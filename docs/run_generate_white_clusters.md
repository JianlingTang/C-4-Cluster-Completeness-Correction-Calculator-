# 跑通「生成 white clusters」与重构后的 Pipeline

重构后，**生成 white 合成图** 和 **detection / matching / dataset** 是两段：

- **生成 white 合成图（SLUG → 白光 → BAOlab → FITS + coords）**  
  仍在 **scripts/** 下的 **legacy 脚本** `generate_white_clusters.py` 里，**尚未迁入** `cluster_pipeline`。
- **重构后的 pipeline**（`cluster_pipeline`）负责：在**已有** synthetic FITS 和 `white_position_*.txt` 的前提下，跑 detection → matching（以及可选的 photometry / catalogue / dataset），配置通过 **env + PipelineConfig**，入口是 **`run_galaxy_pipeline` / `run_ast_pipeline`**。

下面分别说：**重构后怎么跑**、**legacy 脚本怎么跑**、**完整流程怎么串起来**。

---

## 一、重构后的 pipeline（cluster_pipeline）— 需要哪些文件、怎么调用

### 1. 入口与需要的“文件”

- **代码**：`cluster_pipeline` 包（config、matching、detection、pipeline 等）。
- **配置**：通过环境变量或 `get_config(overrides=...)`，**不再**在代码里写死路径（详见 `cluster_pipeline/config/pipeline_config.py`）。
- **输入**：对每个 `(galaxy_id, frame_id, reff)`，需要**已经存在**：
  - 一张 synthetic FITS：在 `config.synthetic_fits_dir(galaxy_id)` 下，匹配 `*_frame{frame_id}_{outname}_reff{reff:.2f}.fits`；
  - 一个 coords 文件：`config.white_dir(galaxy_id) / f"white_position_{frame_id}_{outname}_reff{reff:.2f}.txt"`。

也就是说，**重构后的 pipeline 不会自己去“生成 white clusters”**，只会从已有目录里拷贝这些文件到 temp 目录，再跑 SExtractor 和 matching。

### 2. 环境变量（与默认路径对齐）

| 环境变量 | 含义 | 默认值（与 legacy 一致） |
|----------|------|---------------------------|
| `COMP_MAIN_DIR` | 主目录（星系子目录的父路径） | `/g/data/jh2/jt4478/make_LC_copy` |
| `COMP_FITS_PATH` | 多波段 FITS 根目录 | 同 COMP_MAIN_DIR |
| `COMP_PSF_PATH` | PSF 目录 | `/g/data/jh2/jt4478/PSF_all` |
| `COMP_BAO_PATH` | BAOlab 根目录 | `/g/data/jh2/jt4478/baolab-0.94.1g` |
| `COMP_SLUG_LIB_DIR` | SLUG 库目录 | `/g/data/jh2/jt4478/cluster_slug` |
| `COMP_OUTPUT_LIB_DIR` | 额外 SLUG 库 | `/g/data/jh2/jt4478/output_lib` |
| `COMP_TEMP_BASE_DIR` | 临时目录 | `/tmp/cluster_pipeline` |

不设则用默认值；设了则重构后的 pipeline 全程用这些路径。

### 3. 怎么调用（Python）

```python
from cluster_pipeline.config import get_config
from cluster_pipeline.pipeline import run_galaxy_pipeline

# 用环境变量，或 overrides 覆盖
config = get_config(overrides={"main_dir": "/你的主目录"})

# 跑一个星系：对每个 (frame_id, reff) 从 synthetic_fits + white 拷帧再 detection + matching
run_galaxy_pipeline(
    "ngc628-c_white-R17v100",
    config=config,
    outname="pipeline",
    run_injection=True,   # 会从 config 指向的目录拷贝已有帧/coords
    run_detection=True,
    run_matching=True,
    keep_frames=False,
)
```

或使用 AST 编排（多 frame/reff 可并行）：

```python
from cluster_pipeline.pipeline import run_ast_pipeline

run_ast_pipeline(
    "ngc628-c_white-R17v100",
    config=config,
    outname="pipeline",
    run_injection=True,
    run_detection=True,
    run_matching=True,
    parallel=True,
)
```

**注意**：`run_injection=True` 时，只是从 `synthetic_fits_dir` / `white_dir` **拷贝**已有文件，不会调用 BAOlab 或 SLUG。这些 synthetic FITS 和 `white_position_*.txt` 需要事先由别的方式生成（例如下一节的 legacy 脚本）。

### 4. 只跑前 N 个 stage（max_stage）

Pipeline 按固定顺序分为 6 个 stage，可用 **`max_stage=N`** 只跑前 N 个（1～N 都会跑，N+1～6 不跑）：

| Stage | 名称 | 含义 |
|-------|------|------|
| 1 | injection | 拷贝/生成 synthetic frame + coords |
| 2 | detection | SExtractor 跑图 |
| 3 | matching | 匹配注入 vs 检测坐标；写 matched_coords |
| 4 | photometry | 测光（可选） |
| 5 | catalogue | CI/merr  cuts；in_catalogue |
| 6 | dataset | 拼最终 dataset parquet/npy |

示例：只跑 injection + detection（不跑 matching）：

```python
from cluster_pipeline.config import get_config
from cluster_pipeline.pipeline import run_galaxy_pipeline, STAGE_NAMES

config = get_config()
# 只跑 stage 1 和 2
run_galaxy_pipeline(
    "ngc628-c_white-R17v100",
    config=config,
    outname="pipeline",
    max_stage=2,
)
# 跑满 1～3（injection + detection + matching）
run_galaxy_pipeline("ngc628-c_white-R17v100", config=config, max_stage=3)
```

不传 `max_stage` 时，用原来的 `run_injection` / `run_detection` / `run_matching` 等布尔参数控制。  
`run_ast_pipeline` 同样支持 `max_stage`：

```python
from cluster_pipeline.pipeline import run_ast_pipeline

run_ast_pipeline("ngc628-c_white-R17v100", config=config, max_stage=2, parallel=True)
```

---

## 五、只跑 stage 1–3 并画诊断图（completeness vs magnitude）

若只想跑 **stage 1、2、3**（injection → detection → matching），然后画一张 **x = magnitude、y = completeness** 的诊断图，按下面做。

### 需要的
### 方式一：命令行脚本（推荐）

```bash
cd /Users/janett/Documents/comp_pipeline_restructure

# 先跑 stage 1–3，再画图并保存
python scripts/run_stage123_and_plot_diagnostics.py \
  --galaxy ngc628-c_white-R17v100 \
  --outname pipeline \
  --save completeness_diagnostics.png
```

若已经跑过 stage 1–3，只想重新画图：

```bash
python scripts/run_stage123_and_plot_diagnostics.py \
  --galaxy ngc628-c_white-R17v100 \
  --outname pipeline \
  --no-pipeline \
  --save completeness_diagnostics.png
```

### 方式二：Python 里分步调用

```python
from cluster_pipeline.config import get_config
from cluster_pipeline.pipeline import run_galaxy_pipeline, plot_completeness_diagnostics
import matplotlib.pyplot as plt

config = get_config()

# 1) 只跑 stage 1–3
run_galaxy_pipeline(
    "ngc628-c_white-R17v100",
    config=config,
    outname="pipeline",
    max_stage=3,
    keep_frames=False,
)

# 2) 画 diagnostics：x = magnitude，y = completeness
ax = plot_completeness_diagnostics(
    "ngc628-c_white-R17v100",
    config,
    outname="pipeline",
    n_bins=15,  # magnitude 分 15 个 bin
)
ax.get_figure().savefig("completeness_diagnostics.png", dpi=150, bbox_inches="tight")
plt.show()
```

### 说明

- **Magnitude 来源**：来自注入时的 coords 文件（如 `white_position_*.txt`）的第三列；legacy 脚本生成的是「y x mag」。
- **Completeness**：每个 magnitude bin 内，completeness = 被匹配的注入星数 / 该 bin 内总注入星数。
- **诊断表位置**：`{main_dir}/{galaxy_id}/white/diagnostics/match_summary_frame*_reff*_{outname}.txt`。

---

## 二、Legacy 脚本：真正「生成 white clusters」（未重构进 cluster_pipeline）

**scripts/** 下的 **`generate_white_clusters.py`** 仍然负责：

- 读 SLUG 库、算白光、调用 BAOlab 生成 synthetic FITS；
- 写出 `white_position_{frame}_{outname}_reff{reff}.txt` 等。

它内部路径是**写死**的（如 `/g/data/jh2/jt4478/...`），没有用 `PipelineConfig` 或环境变量。要真实跑通「生成 white clusters」，仍然要：

1. 准备 `--directory` 下的 `galaxy_names.npy`、`galaxy_filter_dict.npy`（同上文）；
2. 保证 SLUG、FITS、PSF、BAOlab 等目录存在且内容符合脚本预期（或改脚本里的路径）。

**最小调用示例**：

```bash
cd /Users/janett/Documents/comp_pipeline_restructure

python scripts/generate_white_clusters.py \
  --gal_name ngc628 \
  --directory /path/to/你的completeness目录 \
  --outname my_run
```

更多参数（`--galaxy_fullname`、`--ncl`、`--mrmodel`、`--eradius_list`、`--validation` 等）见脚本 `argparse` 或本目录下之前写的 run 说明。  
**重要**：脚本里 `fits_path`、`libdir`、`PSFpath`、`baopath` 等仍是硬编码，若你的数据不在 `/g/data/jh2/jt4478/`，需要在脚本里搜索并替换为你的路径。

---

## 四、完整流程：先 legacy 生成 white，再重构 pipeline 跑 detection/matching

1. **用 legacy 脚本生成 synthetic FITS + white coords**  
   运行 **scripts/generate_white_clusters.py**，使输出写到与 `COMP_MAIN_DIR` / `COMP_FITS_PATH` 一致的目录下（或把输出拷到 config 指向的 `main_dir` / `galaxy_id/white/` 等）。
2. **设好环境变量**（或 `get_config(overrides=...)`），使 `synthetic_fits_dir`、`white_dir` 指向刚生成的文件所在位置。
3. **用重构后的 pipeline** 跑 detection + matching：
   - `run_galaxy_pipeline(galaxy_id, config=config, run_injection=True, run_detection=True, run_matching=True)`  
   或  
   - `run_ast_pipeline(...)`。

这样就是「真实跑一遍 generate white clusters（legacy）+ 用重构后的 pipeline 跑后续步骤」的完整流程。

---

## 六、一键安装所有依赖

所有 Python 包 + 外部工具的检查集成到一个脚本：

```bash
# 完整安装（推荐）: venv + pip + 检查 SExtractor/BAOlab
make setup
# 或直接:
bash scripts/setup_env.sh

# 快速安装（仅 Python 包，跳过外部工具检查）
make setup-quick
# 或:
bash scripts/setup_env.sh --quick
```

脚本会自动：

1. 创建 `.venv` 虚拟环境，安装 `requirements.txt` 里的所有 Python 包
2. **安装 SExtractor**：自动尝试 brew（macOS）→ apt（Ubuntu）→ 从 GitHub 源码编译（`--disable-model-fitting`，无需 ATLAS/FFTW）
3. **安装 BAOlab**：自动从 GitHub (`soerenslarsen/baolab`) 克隆、解压 tarball、`make` 编译，安装到 `.deps/local/bin/bl`

**已移除的依赖**：
- **slugpy**：不再需要安装。读取 SLUG 库 FITS 文件的逻辑已内置到 `cluster_pipeline.data.slug_reader`（纯 Python，用 astropy 直接读 FITS + 内嵌 HST 滤镜 Vega zeropoint 表）。不需要 GSL、不需要 C 编译。
- **pyraf**：不再是必须依赖。**scripts/generate_white_clusters.py** 中的 FITS 算术已替换为纯 astropy 实现（`cluster_pipeline.utils.fits_arithmetic`）。仅在跑 stage 4（aperture photometry via IRAF daophot）时才需要 pyraf。

### Makefile 快捷命令

| 命令 | 作用 |
|------|------|
| `make setup` | 完整安装 |
| `make setup-quick` | 仅装 Python 包 |
| `make test` | 跑 pytest |
| `make lint` | flake8 + mypy |
| `make ci` | lint + test |
| `make clean` | 清理 venv 和缓存 |

---

## 七、小结

| 问题 | 答案 |
|------|------|
| 重构了吗？ | 是。detection / matching / config / manifest / dataset 等都在 `cluster_pipeline` 里，用 config 驱动，无路径硬编码。 |
| 「生成 white clusters」在哪儿？ | 在 **`scripts/generate_white_clusters.py`**，尚未迁入 `cluster_pipeline`。 |
| 重构后需要哪些文件、怎么调用？ | 需要**已有** synthetic FITS 和 `white_position_*.txt`；配置用 **env 或 get_config(overrides)**；Python 里调 **run_galaxy_pipeline** 或 **run_ast_pipeline**。 |
| 要真实跑一遍「生成 white」？ | 运行 **`python scripts/generate_white_clusters.py`**，准备好 directory 下的 npy 和 SLUG/FITS/PSF/BAOlab 路径（或改脚本里的硬编码路径）。 |
| 怎么装所有依赖？ | `make setup` 或 `bash scripts/setup_env.sh`，一条命令搞定。不需要装 slugpy / GSL / pyraf。 |
