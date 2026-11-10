"""Generated test images: P5's class-conditional GAN, trained as in P5, used only to test the photo reader.

Adapted from the author's earlier project P5 (repository `generative-ai-applications-project`, notebook
`generative_model.ipynb`): the same generator and discriminator, the same training settings and the same JPEG
storage. The images show the two surrogate mine types of SULAND, which the photo reader never trained on, so they
serve as unfamiliar items. Every image is labelled as generated, and none is ever shown as what an item looks like.

Training data: P5's crops of SULAND (Vivoli et al., 2024, University of Florence; SULAND_v2 labels by Lekhak et al.,
Rochester Institute of Technology), CC BY 4.0, read from P5's repository.

Train, save and write the test images from the repository root:
    python -m triage.generated_images train --p5-data ../generative-ai-applications-project/data
"""
import argparse
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

DATA_DIR = Path("data")
MODELS_DIR = Path("models")
GENERATED_ZIP = "generated_crops_64.zip"
GENERATED_CSV = "generated_manifest.csv"
GENERATED_SHA256 = {   # the generated images as committed (`python -m triage.generated_images train` wrote them)
    GENERATED_ZIP: "899a29423cfd32962473b7f66f9c5bbd6342777a4aa25a94fcb1c48e85f537f6",
    GENERATED_CSV: "11c34e55f6204c06c7e421f323cf44fe228671e4d32c03a1637da1b1de8b2b7a",
}
P5_EXPECTED_SHA256 = {   # P5's data files, as recorded in P5
    "mine_crops_64.zip": "2ddc12cd38dac2b2d621341171b3163d6e7b74d018854b09edabc7cceaa49adb",
    "crops_manifest.csv": "cac0c5593c0b37df522bc7ac3762bf1801d0edf11f5148760c37dbecfe69c286",
}

# P5's fixed settings, unchanged
SEED = 0
THREADS = 2
NZ = 100                 # random numbers the generator turns into an image
WIDTH = 32               # channels in the networks' widest-resolution layer
BATCH = 64
EPOCHS = 40
LEARNING_RATE = 0.0002
BETA1 = 0.5
REAL_TARGET = 1.0
JPEG_QUALITY = 95        # the real crops' quality; every generated image is stored and read back at it
ZIP_TIME = (2026, 1, 1, 0, 0, 0)
N_TYPES = 2              # the two surrogate types, in P5's order (its labels sorted), named "A" and "B" here
GENERATED_PER_TYPE = 50
GENERATED_SEED = SEED + 70   # a seed P5 did not use for its own samples


def file_digest(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_p5_training_crops(p5_data):
    """P5's training crops of the two types, as P5 loaded them: (images in [-1, 1], type numbers)."""
    p5_data = Path(p5_data)
    for name, digest in P5_EXPECTED_SHA256.items():
        if file_digest(p5_data / name) != digest:
            raise ValueError(f"{name} in {p5_data} differs from P5's recorded checksum")
    crops = pd.read_csv(p5_data / "crops_manifest.csv")
    mines = crops[crops.kind == "mine"].reset_index(drop=True)
    with zipfile.ZipFile(p5_data / "mine_crops_64.zip") as archive:
        images = np.stack([np.asarray(Image.open(io.BytesIO(archive.read(n))).convert("RGB")) for n in mines.file])
    order = sorted(mines.label.unique())          # P5's type order
    train_rows = np.flatnonzero((mines.split == "train").to_numpy())
    x = to_unit_range(images[train_rows])
    y = torch.from_numpy(np.array(mines.label.iloc[train_rows].map({t: i for i, t in enumerate(order)})))
    return x, y


def to_unit_range(images):
    """8-bit RGB images (n, 64, 64, 3) to a float tensor (n, 3, 64, 64) in [-1, 1], channel-last in memory."""
    tensor = torch.from_numpy(np.ascontiguousarray(images)).permute(0, 3, 1, 2).float().div(127.5).sub(1)
    return tensor.contiguous(memory_format=torch.channels_last)


def to_8bit(tensor):
    """A float tensor in [-1, 1] back to 8-bit RGB images (n, 64, 64, 3)."""
    return ((tensor.detach().clamp(-1, 1) + 1) * 127.5).round().to(torch.uint8).permute(0, 2, 3, 1).numpy()


class Generator(nn.Module):
    """P5's generator: random numbers and a one-hot type in, a 64 x 64 RGB image in [-1, 1] out."""

    def __init__(self, nz=NZ, width=WIDTH, types=N_TYPES):
        super().__init__()
        w = width
        self.net = nn.Sequential(
            nn.ConvTranspose2d(nz + types, w * 8, 4, 1, 0, bias=False), nn.BatchNorm2d(w * 8), nn.ReLU(True),
            nn.ConvTranspose2d(w * 8, w * 4, 4, 2, 1, bias=False), nn.BatchNorm2d(w * 4), nn.ReLU(True),
            nn.ConvTranspose2d(w * 4, w * 2, 4, 2, 1, bias=False), nn.BatchNorm2d(w * 2), nn.ReLU(True),
            nn.ConvTranspose2d(w * 2, w, 4, 2, 1, bias=False), nn.BatchNorm2d(w), nn.ReLU(True),
            nn.ConvTranspose2d(w, 3, 4, 2, 1, bias=False), nn.Tanh(),
        )

    def forward(self, z, onehot):
        return self.net(torch.cat([z, onehot], dim=1)[:, :, None, None])


class Discriminator(nn.Module):
    """P5's discriminator: a 64 x 64 RGB image and its one-hot type in, one real-or-generated logit out."""

    def __init__(self, width=WIDTH, types=N_TYPES):
        super().__init__()
        w = width
        self.net = nn.Sequential(
            nn.Conv2d(3 + types, w, 4, 2, 1, bias=False), nn.LeakyReLU(0.2, True),
            nn.Conv2d(w, w * 2, 4, 2, 1, bias=False), nn.BatchNorm2d(w * 2), nn.LeakyReLU(0.2, True),
            nn.Conv2d(w * 2, w * 4, 4, 2, 1, bias=False), nn.BatchNorm2d(w * 4), nn.LeakyReLU(0.2, True),
            nn.Conv2d(w * 4, w * 8, 4, 2, 1, bias=False), nn.BatchNorm2d(w * 8), nn.LeakyReLU(0.2, True),
            nn.Conv2d(w * 8, 1, 4, 1, 0, bias=False),
        )

    def forward(self, image, onehot):
        maps = onehot[:, :, None, None].expand(-1, -1, image.shape[2], image.shape[3])
        return self.net(torch.cat([image, maps], dim=1)).view(-1)


def init_weights(module):
    """DCGAN initialisation, as in P5."""
    if isinstance(module, (nn.Conv2d, nn.ConvTranspose2d)):
        nn.init.normal_(module.weight, 0.0, 0.02)
    elif isinstance(module, nn.BatchNorm2d):
        nn.init.normal_(module.weight, 1.0, 0.02)
        nn.init.zeros_(module.bias)


def build_networks():
    """Both networks, initialised from seed 0 in the order P5 used."""
    torch.manual_seed(SEED)
    torch.set_num_threads(THREADS)
    torch.use_deterministic_algorithms(True)
    generator = Generator().to(memory_format=torch.channels_last)
    discriminator = Discriminator().to(memory_format=torch.channels_last)
    generator.apply(init_weights)
    discriminator.apply(init_weights)
    return generator, discriminator


def train_gan(generator, discriminator, x, y, epochs=EPOCHS, seed=SEED, log=print):
    """P5's training loop (non-saturating GAN loss, Adam as in DCGAN); returns the per-epoch history."""
    opt_g = torch.optim.Adam(generator.parameters(), lr=LEARNING_RATE, betas=(BETA1, 0.999))
    opt_d = torch.optim.Adam(discriminator.parameters(), lr=LEARNING_RATE, betas=(BETA1, 0.999))
    bce = nn.BCEWithLogitsLoss()
    order_gen = torch.Generator().manual_seed(seed)
    flip_gen = torch.Generator().manual_seed(seed + 1)
    noise_gen = torch.Generator().manual_seed(seed + 2)
    history = []
    started = time.perf_counter()
    for epoch in range(1, epochs + 1):
        generator.train(); discriminator.train()
        order = torch.randperm(len(x), generator=order_gen)
        totals = dict(d_loss=0.0, g_loss=0.0, d_real=0.0, d_fake=0.0)
        steps = 0
        for start in range(0, len(x) - BATCH + 1, BATCH):
            index = order[start:start + BATCH]
            real = x[index]
            flip = torch.rand(BATCH, generator=flip_gen) < 0.5
            real = torch.where(flip[:, None, None, None], real.flip(3), real)
            onehot = F.one_hot(y[index], N_TYPES).float()
            fake = generator(torch.randn(BATCH, NZ, generator=noise_gen), onehot)

            opt_d.zero_grad()
            real_logit, fake_logit = discriminator(real, onehot), discriminator(fake.detach(), onehot)
            d_loss = bce(real_logit, torch.full_like(real_logit, REAL_TARGET)) + bce(fake_logit, torch.zeros_like(fake_logit))
            d_loss.backward()
            opt_d.step()

            opt_g.zero_grad()
            logit = discriminator(fake, onehot)
            g_loss = bce(logit, torch.ones_like(logit))
            g_loss.backward()
            opt_g.step()

            totals["d_loss"] += d_loss.item(); totals["g_loss"] += g_loss.item()
            totals["d_real"] += torch.sigmoid(real_logit).mean().item(); totals["d_fake"] += torch.sigmoid(fake_logit).mean().item()
            steps += 1
        history.append({"epoch": epoch, **{k: v / steps for k, v in totals.items()}, "seconds": time.perf_counter() - started})
        if epoch == 1 or epoch % 5 == 0:
            h = history[-1]
            log(f"epoch {epoch:>2}: D loss {h['d_loss']:.3f}, G loss {h['g_loss']:.3f}, "
                f"D(real) {h['d_real']:.2f}, D(generated) {h['d_fake']:.2f}, {h['seconds']:.0f} s")
    return pd.DataFrame(history)


def encode_jpeg(array):
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def generate(generator, per_type=GENERATED_PER_TYPE, seed=GENERATED_SEED):
    """per_type images of each type from seeded random inputs, stored as JPEGs and read back as the real crops were."""
    types = np.repeat(np.arange(N_TYPES), per_type)
    z = torch.randn(len(types), NZ, generator=torch.Generator().manual_seed(seed))
    onehot = F.one_hot(torch.from_numpy(types), N_TYPES).float()
    generator.eval()
    with torch.no_grad():
        images = to_8bit(generator(z, onehot))
    jpegs = [encode_jpeg(im) for im in images]
    return jpegs, types


def write_generated(jpegs, types, data_dir=DATA_DIR):
    """A stored zip of the JPEGs, with fixed dates, and a manifest that marks every image as generated."""
    names = [f"generated_{i:03d}.jpg" for i in range(len(jpegs))]
    with zipfile.ZipFile(Path(data_dir) / GENERATED_ZIP, "w", compression=zipfile.ZIP_STORED) as z:
        for name, data in zip(names, jpegs):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    pd.DataFrame({"file": names, "generated": True, "type": ["A" if t == 0 else "B" for t in types],
                  "seed": GENERATED_SEED}).to_csv(Path(data_dir) / GENERATED_CSV, index=False, lineterminator="\n")


def check_generated(data_dir=DATA_DIR):
    """Check the generated images and their manifest against their recorded SHA-256; return {file: True or False}."""
    return {name: file_digest(Path(data_dir) / name) == digest for name, digest in GENERATED_SHA256.items()}


def load_generated(data_dir=DATA_DIR):
    """The generated images (8-bit, (n, 64, 64, 3)) and their manifest, after checking their checksums."""
    checks = check_generated(data_dir)
    if not all(checks.values()):
        raise ValueError(f"generated images differ from their recorded checksums: {checks}")
    manifest = pd.read_csv(Path(data_dir) / GENERATED_CSV)
    with zipfile.ZipFile(Path(data_dir) / GENERATED_ZIP) as archive:
        images = np.stack([np.asarray(Image.open(io.BytesIO(archive.read(n))).convert("RGB")) for n in manifest.file])
    return manifest, images


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["train"])
    parser.add_argument("--p5-data", required=True, help="the data folder of P5's repository")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--models", default=str(MODELS_DIR))
    parser.add_argument("--data", default=str(DATA_DIR))
    args = parser.parse_args()
    x, y = load_p5_training_crops(args.p5_data)
    generator, discriminator = build_networks()
    history = train_gan(generator, discriminator, x, y, epochs=args.epochs)
    models = Path(args.models)
    models.mkdir(parents=True, exist_ok=True)
    torch.save(generator.state_dict(), models / "generator.pt")
    info = {"trained_by": "triage/generated_images.py, P5's settings", "epochs": args.epochs, "seed": SEED,
            "threads": THREADS, "torch": torch.__version__, "training_crops": len(x),
            "history": history.round(6).to_dict(orient="records")}
    (models / "generator.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    jpegs, types = generate(generator)
    write_generated(jpegs, types, args.data)
    print(f"saved {models / 'generator.pt'}; wrote {len(jpegs)} generated images to {Path(args.data) / GENERATED_ZIP}")


if __name__ == "__main__":
    main()
