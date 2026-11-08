"""The photo reader: P4's convolutional network, trained as in P4 on CTX-UXO crops, with its "unknown" band.

Adapted from the author's earlier project P4 (repository `deep-learning-systems-project`, notebook
`deep_learning.ipynb`): the same crops, the same network (UXOCNN), the same training settings, the same
random-erasing augmentation and the same rule for the "unknown" cut-off. Only P4's random-erasing model is trained
here: it was trained on partly hidden crops, and found items are often partly buried or hidden.

Data: CTX-UXO (Craioveanu and Stamatescu, National University of Science and Technology Politehnica Bucharest),
Zenodo record 17052675, CC BY 4.0, cut into 64 x 64 crops in P4. The background crops (no item) come from SULAND
video frames (Vivoli et al., 2024, University of Florence; SULAND_v2 labels by Lekhak et al., Rochester Institute of
Technology), CC BY 4.0, cut in P5.

Train and save from the repository root:  python -m triage.photo_reader train
"""
import argparse
import copy
import hashlib
import io
import json
import math
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image

DATA_DIR = Path("data")
MODELS_DIR = Path("models")
CROPS_ZIP = "ctx_uxo_crops_64.zip"            # one 64 x 64 JPEG crop per labelled object (from P4)
CROPS_CSV = "crops_manifest.csv"              # one row per crop: split, category, source photo, box (from P4)
PHOTOS_CSV = "photos_manifest.csv"            # one row per photo (from P4)
BACKGROUND_ZIP = "background_crops_64.zip"    # 300 crops with no item, from SULAND frames (from P5)
BACKGROUND_CSV = "background_manifest.csv"
EXPECTED_SHA256 = {
    CROPS_ZIP: "9f3cbc88609089864fba9b418c39ec8eb9a97a2451ffdddb2116b1a1695c87c1",
    CROPS_CSV: "4a4322ff01b9390b14e5a7d416676cb1d6e457cf725e5e2ac10aba04f7e8c306",
    PHOTOS_CSV: "53c0c67e9b3d7e704735513f731ab9a437c803e3fd30871d21c385e730eee166",
    BACKGROUND_ZIP: "bca30dd9dadd521a341b9550e155bcc252549632d21de17285ee3626e1895016",
    BACKGROUND_CSV: "1a2e26600105229460d6be914a310aabc8b152dfa884d008527b903c98700017",
}

# P4's fixed settings, unchanged
SEED = 0
THREADS = 2                 # CPU threads, fixed so results do not depend on the computer's core count
CATEGORIES = ["Projectile", "Grenade", "Mortar Bomb", "Cartridge", "Aviation Bomb"]
EPOCHS = 20
BATCH = 64
LEARNING_RATE = 0.001       # lowered along a cosine curve over the epochs
HIDDEN_SHARES = [0.10, 0.25, 0.40]
TARGET_ACCURACY = 0.95      # accuracy the "unknown" cut-off must reach on the validation crops it keeps
UNKNOWN = "unknown"


def set_determinism():
    """Fix the seed, the thread count and deterministic algorithms, as in P4."""
    torch.manual_seed(SEED)
    torch.set_num_threads(THREADS)
    torch.use_deterministic_algorithms(True)


def file_digest(path, algorithm="sha256"):
    """Return the hex digest of a file, reading it in 1 MB chunks."""
    digest = hashlib.new(algorithm)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_data(data_dir=DATA_DIR):
    """Check each data file against its recorded SHA-256; return {file: True or False}."""
    return {name: file_digest(Path(data_dir) / name) == digest for name, digest in EXPECTED_SHA256.items()}


def load_crops(zip_path, names):
    """Read JPEG crops from a zip file into an array of shape (crops, height, width, 3), 8-bit RGB."""
    with zipfile.ZipFile(zip_path) as archive:
        return np.stack([np.asarray(Image.open(io.BytesIO(archive.read(name))).convert("RGB")) for name in names])


def load_background(data_dir=DATA_DIR):
    """The 300 background crops (no item) and their manifest."""
    manifest = pd.read_csv(Path(data_dir) / BACKGROUND_CSV)
    return manifest, load_crops(Path(data_dir) / BACKGROUND_ZIP, manifest.file)


@dataclass
class CropData:
    """P4's crops, split as the dataset's creators split the photos, standardised with the training statistics."""
    crops: pd.DataFrame
    images: np.ndarray
    rows: dict
    unseen_rows: np.ndarray
    channel_mean: torch.Tensor
    channel_std: torch.Tensor
    X: dict
    Y: dict
    X_unseen: torch.Tensor
    class_weights: torch.Tensor

    def to_tensor(self, images):
        """Standardise 8-bit crops of shape (n, 64, 64, 3) into a float tensor of shape (n, 3, 64, 64)."""
        return standardise(images, self.channel_mean, self.channel_std)


def standardise(images, channel_mean, channel_std):
    """8-bit crops (n, 64, 64, 3) to a float tensor (n, 3, 64, 64), channel-last in memory as in P4."""
    x = torch.from_numpy(np.ascontiguousarray(images)).permute(0, 3, 1, 2).float()
    x = x.contiguous(memory_format=torch.channels_last)
    return x.div_(255).sub_(channel_mean[:, None, None]).div_(channel_std[:, None, None])


def load_crop_data(data_dir=DATA_DIR):
    """Load P4's crops and build the training, validation and test tensors exactly as P4 did."""
    crops = pd.read_csv(Path(data_dir) / CROPS_CSV)
    images = load_crops(Path(data_dir) / CROPS_ZIP, crops.crop_file)
    main = crops.category.isin(CATEGORIES).to_numpy()
    labels = crops.category.map({c: i for i, c in enumerate(CATEGORIES)}).fillna(-1).astype(int).to_numpy()
    rows = {split: np.flatnonzero(main & (crops.split == split).to_numpy()) for split in ["train", "valid", "test"]}
    unseen_rows = np.flatnonzero(~main)
    train_unit = torch.from_numpy(images[rows["train"]]).permute(0, 3, 1, 2).float().div(255)
    channel_mean = train_unit.mean(dim=(0, 2, 3))
    channel_std = train_unit.std(dim=(0, 2, 3), correction=0)
    del train_unit
    X = {split: standardise(images[index], channel_mean, channel_std) for split, index in rows.items()}
    Y = {split: torch.from_numpy(labels[index]) for split, index in rows.items()}
    X_unseen = standardise(images[unseen_rows], channel_mean, channel_std)
    train_counts = torch.bincount(Y["train"], minlength=len(CATEGORIES)).float()
    class_weights = train_counts.sum() / (len(CATEGORIES) * train_counts)
    return CropData(crops, images, rows, unseen_rows, channel_mean, channel_std, X, Y, X_unseen, class_weights)


def conv_block(channels_in, channels_out):
    """3 x 3 convolution, batch normalisation, ReLU, then 2 x 2 max pooling (halves height and width)."""
    return nn.Sequential(
        nn.Conv2d(channels_in, channels_out, kernel_size=3, padding=1, bias=False),
        nn.BatchNorm2d(channels_out),
        nn.ReLU(),
        nn.MaxPool2d(2),
    )


class UXOCNN(nn.Module):
    """P4's network: four convolution blocks (32, 64, 128, 256 channels), global average pooling, dropout, linear."""

    def __init__(self, n_classes=len(CATEGORIES), dropout=0.3):
        super().__init__()
        self.features = nn.Sequential(conv_block(3, 32), conv_block(32, 64), conv_block(64, 128), conv_block(128, 256))
        self.classifier = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(dropout), nn.Linear(256, n_classes))

    def forward(self, x):
        return self.classifier(self.features(x))


def flip_and_turn(batch, generator):
    """Flip each crop left to right with probability 0.5, then turn it by a random multiple of 90 degrees."""
    flips = torch.rand(len(batch), generator=generator) < 0.5
    batch = torch.where(flips[:, None, None, None], batch.flip(-1), batch)
    turns = torch.randint(0, 4, (len(batch),), generator=generator)
    out = batch.clone()
    for k in (1, 2, 3):
        chosen = turns == k
        if chosen.any():
            out[chosen] = torch.rot90(batch[chosen], k, dims=(-2, -1))
    return out


def random_erasing(batch, generator, p=0.5, area=(0.02, 0.4), ratio=(0.3, 1 / 0.3)):
    """Hide one random rectangle, filled with random values, in each crop with probability p (Zhong et al., 2020)."""
    out = batch.clone()
    n, channels, height, width = batch.shape
    for i in range(n):
        if torch.rand(1, generator=generator).item() >= p:
            continue
        for _ in range(10):  # retry if the drawn rectangle does not fit
            target_area = torch.empty(1).uniform_(area[0], area[1], generator=generator).item() * height * width
            aspect = math.exp(torch.empty(1).uniform_(math.log(ratio[0]), math.log(ratio[1]), generator=generator).item())
            h = int(round(math.sqrt(target_area * aspect)))
            w = int(round(math.sqrt(target_area / aspect)))
            if h < height and w < width:
                top = int(torch.randint(0, height - h + 1, (1,), generator=generator))
                left = int(torch.randint(0, width - w + 1, (1,), generator=generator))
                out[i, :, top:top + h, left:left + w] = torch.randn(channels, h, w, generator=generator)
                break
    return out


def hide_patches(x, share, rng):
    """Return a copy of crops x with one square patch per crop, covering `share` of it, set to 0 (the average colour)."""
    side = round(x.shape[-1] * math.sqrt(share))
    tops = rng.integers(0, x.shape[-2] - side + 1, len(x))
    lefts = rng.integers(0, x.shape[-1] - side + 1, len(x))
    hidden = x.clone()
    for i, (top, left) in enumerate(zip(tops, lefts)):
        hidden[i, :, top:top + side, left:left + side] = 0.0
    return hidden


def predict(model, x, batch=512):
    """Return the model's logits for crops x, in evaluation mode."""
    model.eval()
    with torch.no_grad():
        return torch.cat([model(x[i:i + batch]) for i in range(0, len(x), batch)])


def confusion(y_true, y_pred, k=len(CATEGORIES)):
    """Return the k x k matrix of counts: rows are true categories, columns predicted ones."""
    return np.bincount(np.asarray(y_true) * k + np.asarray(y_pred), minlength=k * k).reshape(k, k)


def scores(y_true, y_pred):
    """Accuracy, macro-F1, and precision, recall and F1 for each category."""
    matrix = confusion(y_true, y_pred)
    true_positive = np.diag(matrix).astype(float)
    precision = np.divide(true_positive, matrix.sum(axis=0), out=np.zeros(len(matrix)), where=matrix.sum(axis=0) > 0)
    recall = np.divide(true_positive, matrix.sum(axis=1), out=np.zeros(len(matrix)), where=matrix.sum(axis=1) > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(len(matrix)), where=precision + recall > 0)
    return {"accuracy": true_positive.sum() / matrix.sum(), "macro_f1": f1.mean(),
            "precision": precision, "recall": recall, "f1": f1}


def train_reader(data, epochs=EPOCHS, log=print):
    """Train P4's random-erasing model and keep the weights of the epoch with the best validation macro-F1."""
    set_determinism()
    model = UXOCNN()
    optimiser = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=epochs)
    loss_fn = nn.CrossEntropyLoss(weight=data.class_weights)
    order_generator = torch.Generator().manual_seed(SEED)
    turn_generator = torch.Generator().manual_seed(SEED + 1)
    erase_generator = torch.Generator().manual_seed(SEED + 2)
    n = len(data.X["train"])
    history, best = [], (-1.0, 0, None)
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        model.train()
        rate = optimiser.param_groups[0]["lr"]
        order = torch.randperm(n, generator=order_generator)
        running = 0.0
        for start in range(0, n, BATCH):
            batch = order[start:start + BATCH]
            x = random_erasing(flip_and_turn(data.X["train"][batch], turn_generator), erase_generator)
            optimiser.zero_grad()
            loss = loss_fn(model(x), data.Y["train"][batch])
            loss.backward()
            optimiser.step()
            running += loss.item() * len(batch)
        schedule.step()
        logits = predict(model, data.X["valid"])
        valid = scores(data.Y["valid"].numpy(), logits.argmax(1).numpy())
        history.append({"epoch": epoch, "learning rate": rate, "train loss": running / n,
                        "validation loss": loss_fn(logits, data.Y["valid"]).item(),
                        "validation accuracy": valid["accuracy"], "validation macro-F1": valid["macro_f1"]})
        log(f"epoch {epoch:>2}: train loss {running / n:.3f}, validation macro-F1 {valid['macro_f1']:.3f} "
            f"({time.perf_counter() - started:.0f} s)")
        if valid["macro_f1"] > best[0]:
            best = (valid["macro_f1"], epoch, copy.deepcopy(model.state_dict()))
    model.load_state_dict(best[2])
    seconds = time.perf_counter() - started
    log(f"best validation macro-F1 {best[0]:.3f} at epoch {best[1]}; those weights are kept ({seconds:.0f} s in all)")
    return model, pd.DataFrame(history).set_index("epoch"), best[1], seconds


def unknown_cutoff(model, data, target=TARGET_ACCURACY):
    """P4's rule: the lowest confidence at which the validation crops kept reach the target accuracy."""
    probabilities = predict(model, data.X["valid"]).softmax(1)
    confidence, predicted = probabilities.max(1)
    order = torch.argsort(confidence, descending=True, stable=True)
    correct = (predicted[order] == data.Y["valid"][order]).double()
    accuracy = (correct.cumsum(0) / torch.arange(1, len(order) + 1)).numpy()
    reached = np.flatnonzero(accuracy >= target)
    return float(confidence[order].numpy()[reached[-1]]) if len(reached) else 1.0


class PhotoReader:
    """Reads one 64 x 64 crop of the item a person marked: a category with its confidence, or "unknown"."""

    def __init__(self, model, channel_mean, channel_std, cutoff, info=None):
        self.model = model.eval()
        self.channel_mean = channel_mean
        self.channel_std = channel_std
        self.cutoff = cutoff
        self.info = info or {}

    def probabilities(self, images):
        """Class probabilities for 8-bit crops of shape (n, 64, 64, 3)."""
        return predict(self.model, standardise(images, self.channel_mean, self.channel_std)).softmax(1)

    def read(self, images):
        """One verdict per crop: {"category": a category or "unknown", "confidence": ..., "best_guess": ...}."""
        verdicts = []
        for p in self.probabilities(images):
            confidence, index = p.max(0)
            best = CATEGORIES[int(index)]
            verdicts.append({"category": best if confidence.item() >= self.cutoff else UNKNOWN,
                             "confidence": round(confidence.item(), 4), "best_guess": best})
        return verdicts

    def save(self, models_dir=MODELS_DIR):
        models_dir = Path(models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), models_dir / "photo_reader.pt")
        info = dict(self.info, categories=CATEGORIES, cutoff=self.cutoff,
                    channel_mean=self.channel_mean.tolist(), channel_std=self.channel_std.tolist())
        (models_dir / "photo_reader.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, models_dir=MODELS_DIR):
        models_dir = Path(models_dir)
        info = json.loads((models_dir / "photo_reader.json").read_text(encoding="utf-8"))
        model = UXOCNN()
        model.load_state_dict(torch.load(models_dir / "photo_reader.pt", weights_only=True))
        return cls(model, torch.tensor(info["channel_mean"]), torch.tensor(info["channel_std"]), info["cutoff"], info)


def train_and_save(data_dir=DATA_DIR, models_dir=MODELS_DIR, epochs=EPOCHS, log=print):
    """Check the data, train the reader, set its cut-off and save both."""
    checks = check_data(data_dir)
    if not all(checks.values()):
        raise ValueError(f"data files differ from their recorded checksums: {checks}")
    data = load_crop_data(data_dir)
    model, history, best_epoch, seconds = train_reader(data, epochs=epochs, log=log)
    cutoff = unknown_cutoff(model, data)
    info = {"trained_by": "triage/photo_reader.py, P4's random-erasing settings", "epochs": epochs,
            "best_epoch": best_epoch, "training_seconds": round(seconds), "threads": THREADS, "seed": SEED,
            "torch": torch.__version__, "numpy": np.__version__,
            "history": history.reset_index().round(6).to_dict(orient="records")}
    reader = PhotoReader(model, data.channel_mean, data.channel_std, cutoff, info)
    reader.save(models_dir)
    log(f"cut-off {cutoff:.4f}; saved to {Path(models_dir) / 'photo_reader.pt'}")
    return reader, data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["train", "check"])
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--models", default=str(MODELS_DIR))
    args = parser.parse_args()
    if args.command == "check":
        print(check_data())
    else:
        train_and_save(models_dir=args.models, epochs=args.epochs)


if __name__ == "__main__":
    main()
