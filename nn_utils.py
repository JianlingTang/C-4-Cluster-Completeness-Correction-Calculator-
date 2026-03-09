# utils
import matplotlib.pyplot as plt
import numpy as np


############# plotting ####################
def plot_train_val_loss(hist, title, outpath):
    plt.figure(figsize=(6, 4))
    plt.plot(hist["train_loss_epoch"], label="train CE")
    plt.plot(hist["val_loss_epoch"], label="val CE")
    plt.xlabel("epoch")
    plt.ylabel("cross-entropy loss")
    plt.legend()
    plt.title(title)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()


def scatter_param_vs_val(results, x_key, title, outpath, save_values_path=None):
    xs, ys = [], []
    for cfg, _ in results:
        xs.append(cfg[x_key])
        ys.append(cfg["final_val_loss"])

    plt.figure(figsize=(5, 4))
    plt.scatter(xs, ys, alpha=0.8)
    plt.xscale("log")
    plt.xlabel(x_key)
    plt.ylabel("final validation CE")
    plt.title(title)
    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

    if save_values_path is not None:
        np.savez(
            save_values_path,
            x=xs,
            val_loss=ys,
        )

def plot_lr_wd_grid(results, title, outpath, save_values_path=None):
    """
    2D grid: x=log10(max_lr), y=log10(weight_decay),
    color=val_loss
    """

    lrs = np.array([cfg["max_lr"] for cfg, _ in results])
    wds = np.array([cfg["weight_decay"] for cfg, _ in results])
    losses = np.array([cfg["final_val_loss"] for cfg, _ in results])

    log_lrs = np.log10(lrs)
    log_wds = np.log10(wds)

    plt.figure(figsize=(6, 5))
    sc = plt.scatter(
        log_lrs,
        log_wds,
        c=losses,
        cmap="viridis",
        s=120,
        edgecolor="k",
    )

    plt.xlabel("log10(max_lr)")
    plt.ylabel("log10(weight_decay)")
    plt.title(title)

    cbar = plt.colorbar(sc)
    cbar.set_label("final validation CE")

    plt.tight_layout()
    plt.savefig(outpath, dpi=150)
    plt.close()

    # ---- save raw data ----
    if save_values_path is not None:
        np.savez(
            save_values_path,
            max_lr=lrs,
            weight_decay=wds,
            log10_max_lr=log_lrs,
            log10_weight_decay=log_wds,
            val_loss=losses,
        )

###########################################
