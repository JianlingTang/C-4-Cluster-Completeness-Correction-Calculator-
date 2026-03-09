# 本地安装 IRAF（用于五色 photometry）

PyRAF 已通过 `pip install pyraf` 安装在项目 `.venv` 中。要跑带 photometry 的完整流程，还需安装 **IRAF** 并设置环境变量。

## Apple Silicon (M1/M2/M3) 一键安装

安装包已下载到项目中，只需在本机执行：

```bash
# 1. 去掉 quarantine（否则 macOS 可能阻止安装）
xattr -c .deps/iraf_download/iraf-2.18.1-1-arm64.pkg

# 2. 打开安装器（会提示输入登录密码）
open .deps/iraf_download/iraf-2.18.1-1-arm64.pkg
```

按安装向导点击「继续」，在需要时输入本机密码。默认会装到 `/usr/local/lib/iraf/`。

## 从头到尾跑一遍（含 photometry → detection_*.npy）

安装好 IRAF 后，在项目根目录执行：

```bash
chmod +x scripts/run_full_with_iraf.sh
./scripts/run_full_with_iraf.sh
```

该脚本会设置 `IRAF=/usr/local/lib/iraf` 并调用：

```bash
python scripts/run_small_test.py --input_coords ngc628-c/white/input_coords_500.txt --run_photometry
```

会依次执行：Phase A 注入 → 准备五色 frame → Phase B（detection + matching + 五色 photometry + CI cut）→ 输出 `detection_*.npy` 与 completeness 诊断图。

## 若未装 IRAF 直接跑

不装 IRAF 也可以跑同一命令，但 photometry 会跳过，只得到 white-match 的 label 和诊断图：

```bash
.venv/bin/python scripts/run_small_test.py --input_coords ngc628-c/white/input_coords_500.txt --run_photometry
```
