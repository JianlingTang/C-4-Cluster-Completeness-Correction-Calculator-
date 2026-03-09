# Completeness 流程：用了哪些 script、怎么跑、有哪些假设

## 0. Photometry / CI cut 的正确逻辑（当前实现）

- **不是**在 white synthetic 图上做 5-filter photometry，也不是把同一张 white 图复制到 5 个 filter。
- **是**：用白光 detection + matching 得到 **matched_coords**（同一批 cluster，同一套坐标）；把这些人造星 **inject 到真实的 HLSP … F*W drc/sci 科学图上**（每个 filter 一张科学图），得到「科学图 + 注入」的 FITS；再在这张图上用 **matched_coords** 做 photometry 和 CI cut。
- 同一 cluster 在 white 和 5 个 filter 上 **坐标一致**（都是 matched 位置）；各 filter 的星等来自 physprop 的 `mag_VEGA_select`（每 filter 一列）。

实现上：pipeline 在 run_photometry 时若配置了 `inject_5filter_script`，会先按 matched_coords + physprop 写出每 filter 的 `(x, y, mag)` 文件，再调用 **scripts/inject_clusters_to_5filters.py**（`--use_white`）把这些人造源打到 HLSP 科学图上，输出写到各 filter 的 `synthetic_fits/`，供后续 photometry 使用。

---

## 1. 涉及的脚本与入口

| 脚本 | 作用 | 谁调用 |
|------|------|--------|
| **`scripts/run_small_test.py`** | 总入口：串起 Phase A → Phase B，可选 backfill + 画 completeness 图 | 用户直接运行 |
| **`scripts/generate_white_clusters.py`** | Phase A：生成白光 synthetic 图、写 `white_position_*`、写 **physprop**（若未用 `--input_coords` 则从 SLUG 采样） | `run_small_test.run_phase_a()` 里 `subprocess.run(scripts/generate_white_clusters.py ...)` |
| **`cluster_pipeline.pipeline.pipeline_runner.run_galaxy_pipeline`** | Phase B：用已有 white 图和 coords 做 detection → matching → 可选 photometry → catalogue，写 labels、match_summary、catalogue 等 | `run_small_test.run_phase_b()` |
| **`run_small_test.backfill_physprop_from_white_coords()`** | 在**没有**由 generate_white_clusters 写出 physprop 时，用 `white_position_*` + 可选 input_coords 补写 physprop | `run_small_test` 在 `--plot_only` 或 `--run_photometry` 且 nframe>1 时调用 |
| **`run_small_test.plot_completeness_diagnostics()`** | 读 labels + physprop，画 completeness vs mass / age / mag(5 bands) | `run_small_test` 在 plot_only 或 run_photometry 结束后调用 |
| **`scripts/inject_clusters_to_5filters.py`** | 把 matched 星团（同坐标）按每 filter 星等 inject 到 HLSP 科学图，写出 `galaxy/filter/synthetic_fits/*.fits` | 由 pipeline（当 `inject_5filter_script` 已配置时）在每 frame matching 后、photometry 前调用 |

没有单独跑 `scripts/perform_photometry_ci_cut_on_5filters.py` 或 `cluster_pipeline.pipeline.diagnostics.plot_completeness_diagnostics`；completeness 图只来自 **run_small_test** 里的 `plot_completeness_diagnostics()`。

---

## 2. 典型怎么跑

### 2.1 只画图（不跑注入 / pipeline）

```bash
python scripts/run_small_test.py --plot_only --nframe 10
```

- **不跑** Phase A、Phase B。
- 若 `nframe > 1`：先 `backfill_physprop_from_white_coords(nframe)`，再 `plot_completeness_diagnostics(nframe)`。
- **假设**：  
  - 已有 `ngc628-c/white/white_position_{0..nframe-1}_test_reff3.00.txt`；  
  - 已有 `ngc628-c/white/detection_labels/detection_frame{i}_*` 或 `detection_labels_white_match_frame{i}_*`；  
  - backfill 会**生成/覆盖** `physprop/*_frame{i}_*`，mag 来自 `white_position_*` 最后一列，mass/age 来自 `input_coords`（若 5 列）或默认 `ngc628-c/white/input_coords_500.txt`（若存在且 5 列）或 SLUG 循环。

### 2.2 完整跑（注入 + detection + matching，不跑 photometry）

```bash
python scripts/run_small_test.py --nframe 1 --ncl 20
# 或
python scripts/run_small_test.py --input_coords path/to/x_y_mag.txt --nframe 10
```

- Phase A：`scripts/generate_white_clusters.py` → 生成 white 图、`white_position_*`、**physprop**（无 `--input_coords` 时由 SLUG 写；有 `--input_coords` 时由 generate_white_clusters 按该文件写，若 5 列则含 mass/age）。
- Phase B：`run_galaxy_pipeline(max_stage=3)` → 只做 detection + matching，写 `matched_coords`、`match_summary_*`、**white-match labels**（`detection_labels_white_match_*`），**不写** `detection_frame_*`（最终 photometry+CI 的 label）。
- **不** backfill，**不**画图（除非你后面再单独加画图逻辑）。

### 2.3 注入 + pipeline 到 photometry + 画图

```bash
python scripts/run_small_test.py --run_photometry --nframe 10 --ncl 500
# 或
python scripts/run_small_test.py --run_photometry --input_coords path/to/5col.txt --nframe 10
```

- Phase A：同上，生成 white 图、`white_position_*`、physprop（若 generate_white 写了的话）。
- Phase B：`run_galaxy_pipeline(max_stage=5, run_photometry=True, run_catalogue=True)`。  
  - 对每个 frame：matching 后若配置了 `inject_5filter_script`（且存在 physprop mag_VEGA 与 matched_coords + cluster_ids），则先 **写出每 filter 的 (x,y,mag) coord 文件**（`white/{Filt}_position_{frame}_{outname}_reff{reff}.txt`），再 **调用 inject_clusters_to_5filters.py --use_white** 把 matched 星团打到 HLSP 5-filter 科学图上，输出写入各 filter 的 `synthetic_fits/`。  
  - 然后在该 frame 的「科学图+注入」FITS 上跑 5-filter photometry + CI/merr，写 catalogue 与 **detection_frame_*.npy**。
- 若 nframe>1 且传了 `--input_coords`：再 `backfill_physprop_from_white_coords(...)`（可能覆盖 physprop）。
- 最后 `plot_completeness_diagnostics(nframe)` 画图。

---

## 3. 数据流与顺序约定（画图用到的）

画图时假设**同一索引 = 同一星团**：

- **labels**：`detection_frame{i}_*` 或 `detection_labels_white_match_frame{i}_*`，长度 = 该 frame 注入数 ncl，顺序 = **cluster_id 0..ncl-1**（= 注入顺序）。
- **physprop**：`mass_select_*_frame{i}_*`、`age_select_*_frame{i}_*`、`mag_VEGA_select_*_frame{i}_*`，每块长度 ncl，顺序 = **该 frame 注入顺序**（与 white_position 行顺序一致）。

多 frame 时：按 frame 0, 1, …, nframe-1 依次 concatenate，所以  
`labels[j]`、`mass[j]`、`age[j]`、`mag_5[j]` 对应**同一星团**（某 frame 的某一行）。

---

## 4. 关键假设（以及何时会违反）

| 假设 | 何时成立 | 何时会破 |
|------|----------|----------|
| **labels 与 physprop 行对齐** | 每个 frame 的 labels 和 physprop 都是按同一注入顺序写、且只从 run_small_test + pipeline 这一条链路产生 | 若 physprop 被 backfill 用**另一份** input_coords（如 500 行）写，而 labels 是 10×500=5000，则 backfill 对 frame 1..9 仍用 `ic_mass[:500]`，即**同一 500 个 mass/age 重复 10 次**；只有 mag 是每 frame 从 white_position 读的，所以 **mass/age 面板错位**，mag 面板按“每 frame 内”仍对齐 |
| **mag 横轴 = 真实各 band 星等** | 用 generate_white 生成的 physprop，且每个 filter 有**各自**的合成图与星等 | 若用 backfill：mag 来自 white_position 最后一列（白光），再被**复制成 5 列**，所以 5 个 mag 子图本质是**同一套白光 mag**；若用 run_photometry 但 5 个 filter 的图都是**同一张 white 的拷贝**，则测光是在同一张图上做 5 次，横轴“F275W/F555W/…” 只是标签，**不是**真实各 band 的注入星等 |
| **completeness vs mag 呈 logistic** | 检测概率随星等单调、且横轴是“该 band 真实星等”、且 binning 是物理星等区间 | 横轴是白光 mag 或“假”的 5 band 复制；或 labels 是“after photometry+CI”（亮星被 CI/merr 砍）；或 binning 用百分位导致横轴/顺序乱 |
| **physprop 来自 generate_white 且 1:1** | 没开 backfill，或 backfill 只用与**当前 run** 一致的 input_coords（行数 = ncl×nframe） | `--plot_only` 或 run_photometry 后对 nframe>1 用默认 `input_coords_500.txt` 做 backfill → mass/age 只有 500 行，被 `ic_mass[:ncl]` 重复用到每一 frame |

---

## 5. 总结：为什么图会“不对”

1. **脚本链**：只用了 `run_small_test.py` → Phase A（scripts/generate_white_clusters.py）+ Phase B（run_galaxy_pipeline）+ 可选 backfill + `plot_completeness_diagnostics()`。没有用 scripts/perform_photometry_ci_cut_on_5filters 或 pipeline 里另一套 diagnostics 画图。
2. **5 个 filter 的图**：要么是 backfill 把**白光 mag 复制 5 列**（5 张 mag 子图同一套 x），要么是 photometry 跑在**同一张 white 图复制到 5 个 filter** 上，横轴都不是“各 band 真实注入星等”，所以 completeness vs mag 不必、也往往不会呈标准 logistic。
3. **mass/age**：nframe>1 且 backfill 用 500 行 input_coords 时，只有 frame 0 的 mass/age 与 labels 对齐，frame 1..9 的 mass/age 是重复的 500 行，**错位**。
4. **Binning**：mag 已改为固定星等 bin + 按 x 排序，但若数据本身不对齐或横轴含义不是“真实 band 星等”，曲线形状仍会怪。

若要“对的” completeness vs mag（logistic 形状、物理意义清晰），需要：  
- 要么只画 **vs 白光 mag** 一张图，且 mag 和 labels 都来自同一 run、同一顺序；  
- 要么用**各 filter 各自**的 synthetic 图和注入星等，再跑 photometry，再用对应 physprop 的各 band mag 画 5 张图。
