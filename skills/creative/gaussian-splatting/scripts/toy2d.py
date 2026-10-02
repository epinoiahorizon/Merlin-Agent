"""toy2d.py — Gaussian Splatting formula verification, 2D toy (CPU, ~30s).

Implements the exact equations from ~/.merlin/skills/creative/gaussian-splatting:
    Σ  = R diag(s²) Rᵀ                       (anisotropic covariance from factors)
    D  = exp(−½ dᵀ Σ⁻¹ d)                    (Gaussian density at pixel; d = pixel − µ)
    αᵢ = opacityᵢ · Dᵢ                        (clamped 0–0.99)
    C  = Σᵢ αᵢ Tᵢ cᵢ,  Tᵢ = Π_{j<i}(1−αⱼ)      (depth-sorted alpha compositing)
    loss = MSE(render, target), Adam lr=0.05, 200 steps  (the skill's recipe)

Success criterion (skill's): 64 splats must snap into a red circle + blue square,
final MSE < 0.02 — proving the formula chain is not decorative; it's executable.
"""
import math
import sys
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.manual_seed(0)
SIZE = 64


def make_target(size=SIZE):
    yy, xx = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    img = np.zeros((size, size, 3), dtype=np.float32)
    img[(xx - 20) ** 2 + (yy - 20) ** 2 < 10 ** 2] = [1.0, 0.2, 0.2]
    img[(np.abs(xx - 45) < 8) & (np.abs(yy - 40) < 8)] = [0.2, 0.3, 1.0]
    return torch.from_numpy(img)


class Splats2D(nn.Module):
    """Same parameter set as 3DGS: µ(2), log-scale(2), rot(1), colour logits(3), opacity logit(1)."""

    def __init__(self, G=64, size=SIZE, seed=0):
        super().__init__()
        g = torch.Generator().manual_seed(seed)
        self.means = nn.Parameter(
            torch.rand(G, 2, generator=g) * torch.tensor([size, size], dtype=torch.float32))
        self.log_scale = nn.Parameter(torch.ones(G, 2) * math.log(2.0))
        self.rot = nn.Parameter(torch.zeros(G))
        self.colour_logits = nn.Parameter(torch.randn(G, 3, generator=g) * 0.5)
        self.opacity_logit = nn.Parameter(torch.zeros(G))
        self.depth = nn.Parameter(torch.rand(G, generator=g))

    def covs(self):
        s = torch.exp(self.log_scale)
        c, si = torch.cos(self.rot), torch.sin(self.rot)
        R = torch.stack([torch.stack([c, -si], -1), torch.stack([si, c], -1)], -2)
        S = torch.diag_embed(s ** 2)
        return R @ S @ R.transpose(-1, -2)

    def render(self, size=SIZE):
        G = self.means.shape[0]
        inv = torch.linalg.inv(self.covs())
        yy, xx = torch.meshgrid(torch.arange(size, dtype=torch.float32),
                                torch.arange(size, dtype=torch.float32), indexing="ij")
        pts = torch.stack([xx, yy], -1).view(-1, 2)
        diff = pts[None, :, :] - self.means[:, None, :]
        d = torch.einsum("gpi,gij,gpj->gp", diff, inv, diff)
        density = torch.exp(-0.5 * d)
        alphas = (torch.sigmoid(self.opacity_logit)[:, None, None]
                  * density.view(G, size, size)).clamp(0, 0.99)
        out = torch.zeros(size, size, 3)
        T = torch.ones(size, size)
        for i in torch.argsort(self.depth):
            a = alphas[i]
            out = out + (T * a)[..., None] * torch.sigmoid(self.colour_logits[i])[None, None, :]
            T = T * (1 - a)
        return out


def main():
    target = make_target()
    model = Splats2D()
    opt = torch.optim.Adam(model.parameters(), lr=0.05)
    for step in range(200):
        pred = model.render()
        loss = F.mse_loss(pred, target)
        opt.zero_grad()
        loss.backward()
        opt.step()
        if step % 40 == 0 or step == 199:
            print(f"step {step:3d}  mse {loss.item():.4f}")
    final = loss.item()
    print(f"FINAL MSE: {final:.4f}")
    if final >= 0.02:
        print(f"FAIL — target < 0.02, got {final:.4f}")
        return 1
    # pixel-accurate check: fraction of pixels within 0.2 of the target
    with torch.no_grad():
        close = ((pred - target).abs() < 0.2).all(-1).float().mean().item()
    print(f"pixels within 0.2 of target: {close * 100:.1f}%")
    print("PASS — Σ=R diag(s²)Rᵀ, exp(−½dᵀΣ⁻¹d), depth-sorted alpha blend confirmed")
    return 0


if __name__ == "__main__":
    sys.exit(main())