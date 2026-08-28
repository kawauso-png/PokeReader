# Suicune Deep Probe v3.6 — Direct Phase Collector

## 目的

v3.5 で `0x0022F604` の値を各 rDIV read で直接記録できるようになった。
0062 では、これを DIV byte と組み合わせた直接位相が停止1/停止2の実測と整合した。

v3.6 は追加の広域ダンプを行わない。次の2実験に必要なデータ収集を軽量化・明確化する。

1. `Δ1 = f(target_asub)` かを 8〜10 run で判定する。
2. 同じ `target_asub` の2 run で、通常フレームの微小揺れ列が再現するかを判定する。

## 重要な表記修正

v3.5 の `target_a12 / target_s12` は「A」ではなく、直接読んだ絶対位相 `P` の整数部分だった。
v3.6 では誤解を避けて `P4` として保存する。

```
P4_A = ((A_DIV << 6) | ASUB) mod 16384
P4_S = ((S_DIV << 6) | SSUB) mod 16384
P_A  = P4_A / 4
P_S  = P4_S / 4
```

`P4` の1単位は1 M-cycle = 4 T-cycle = 0.25 A-unit。

CSV の `asub` / `ssub` は16進表示なので、v3.6 は `asub_dec / ssub_dec` も同時に保存する。
例えば `asub=16` は **0x16 = 22 decimal**。

## CSV追加/変更

Probe summary:

- `target_asub`, `target_ssub` — hex
- `target_asub_dec`, `target_ssub_dec` — decimal
- `target_ap4`, `target_sp4` — exact direct phase in M-cycle units
- `target_sub_bucket` — `target_asub >> 3`, B0〜B7
- legacy `phase_a / phase_s` は比較用として残す

Frame section:

- `asub`, `ssub` — hex
- `asub_dec`, `ssub_dec` — decimal
- `ap4`, `sp4` — direct phase

Call/Deep の `mcycle` は v3.5 同様に保持する。

## 画面表示

Probe OFF 中も RNG ページに現在の subtick を表示する。

```
LiveSub 16/21 B2
```

Y+X でARMした後は、固定されたTarget値を表示する。

```
TSub 16/21 B2 D0
P4 10D6/10E1
```

これにより、B0〜B7へ散るようにTargetを選びやすくなる。

## 実験1: Δ1 vs target_asub

まず 8〜10本。
目安として B0〜B7 を最低1本ずつ取る。
同じTarget Advanceである必要はない。
今回の目的は shiny hit ではなく位相関係の測定なので、任意のTargetでよい。

Pause中に RNG 画面の `LiveSub` を見て、必要なら単フレーム進行でbucketを変えてから Y+X でARMする。

通常の操作:

```
TargetでPause
Y+X   Deep Probe ARM
Y+B   Fixed A Frame ARM
↑保持
Y+L
Y/Lだけ離す
2F完了
↑離す
R
hands off
```

## 実験2: 同一 target_asub 再現性

8〜10本が集まったら、既に出た `target_asub` と完全一致する値をもう1本取る。
Bucket一致ではなく exact byte 一致を優先する。

## 解析

```
python3 analyze_suicune_phase_v36.py celebi_trace_0062.csv
```

複数:

```
python3 analyze_suicune_phase_v36.py trace1.csv trace2.csv ... --out phase_collection.csv
```

出力:

- target_asub / bucket / P
- 02B6→02BE pair gap 分布
- repeated-advance stall の直接 `extra M`
- stop1 の historical fit sign Δ1
- stop2 の余剰位相
- 通常フレームの micro jitter
- 同一 target_asub run 間の jitter exact-match率
- 集計CSV

解析スクリプトでは通常遷移のうち `|step-1172| <= 10M` を micro-jitter core として別集計し、それを超えるイベント由来/構造的遷移を隠さず除外件数として表示する。

## 0062の注意

0062 summary の `target_asub=16` はCSV上16進なので **0x16 = decimal 22**。
このhex/decimal曖昧さをv3.6で解消した。
