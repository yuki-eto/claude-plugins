# オーディオとタイミング

音楽に同期させる処理（リズムゲーム、ビートに合わせた演出、拍にスナップする SE）があるゲーム向けの章。BGM と効果音を鳴らすだけなら、最後の「読み込み」の節だけ読めばよい。

## 曲の時計（Song Clock）

### 再生位置は毎回オーディオサーバーから計算する

```
songTime = player.GetPlaybackPosition()
         + AudioServer.GetTimeSinceLastMix()
         - EffectiveOutputLatencySec
```

- フレームの `delta` を足し合わせて求めない（ずれが蓄積する）
- `GetTimeSinceLastMix()` で、最後のミックス時点から「今」まで進める
- 出力レイテンシを引くと「今まさに聞こえている位置」になる

### 1 フレームに 1 回だけ計算し、後戻りを防ぐ

- 上の 2 つの読み取りはアトミックではないので、同じフレームの中で読み直すと、値が最大でミックスバッファ 1 個分（約 12ms）**戻る**ことがある
- 戻った値をグリッドに量子化すると、同じグリッド位置を 2 回通ってしまう（実例: SE の二重再生）
- 対策:
  - 計算は `Engine.GetProcessFrames()` をキーにして、1 フレームに 1 回だけ行う（遅延計算 + キャッシュ）
  - 計算した値を、小さな後戻りを無視するフィルタに通す

```csharp
public static double Filter(double previous, double candidate, double wrapThresholdSec)
{
    bool smallRegression = candidate < previous && previous - candidate < wrapThresholdSec;
    return smallRegression ? previous : candidate;
}
```

- このしきい値（例: 0.5 秒）は、ループの巻き戻しを検出するしきい値と同じ値にする。フィルタが握りつぶす後戻りを、巻き戻し検出が必要とすることがあってはならない
- 時刻の参照元は 1 つにまとめる。生の `GetPlaybackPosition()` を別の場所で読まない

### 出力レイテンシ

- `AudioServer.GetOutputLatency()` は、iOS では実装されておらず、macOS でも約 0 を返すことがあった
- しきい値以下なら、プロジェクト設定 `audio/driver/output_latency`（既定 15ms）を代わりに使うプロパティ `EffectiveOutputLatencySec` を用意する
- **レイテンシを引く処理と足し戻す処理は、必ず同じプロパティを使う。** 別々に `GetOutputLatency()` を読むと値が食い違う

### ビートの計算は Core に置く

BPM、オフセット、スウィング、グリッドへの量子化、拍番号から時刻への変換は、純粋な関数として Core に置き（例: `BeatGrid`）、xUnit でテストする。Godot 側の時計はそれを呼ぶだけにする。

## 予約再生（`start(when)` は存在しない）

Godot には、WebAudio の `AudioBufferSourceNode.start(when)` のように「将来の時刻を指定して再生を予約する」API がない。そのため、**目標時刻を保持しておき、ポーリングで到達を検出したら `Play()` する**形にする。

### 方式の選び方

| 方式 | 精度 | 用途 |
|---|---|---|
| `_Process()` で毎フレーム確認 | ±0.5 フレーム（60fps で約 ±8ms） | ボイス・演出など、多少ずれてもよいもの |
| 専用スレッドで 1ms ごとに確認 | 約 1ms | 拍にスナップする SE（60fps ではフレーム単位のずれが耳で分かった） |

`SignalTimer` や `await ToSignal(GetTree().CreateTimer(...))` で代用しない。ほかのタイミング判断と同じ時計に基づかないため。

### 専用スレッド方式の作り方

- ワーカースレッドからは、曲の時計（Node の API）を直接読まない
- メインスレッドが毎フレーム `{songTime, outputLatency, playing, 実時刻}` をロック付きの箱（`SongTimeAnchor`）に書き込み、ワーカーは経過した実時刻の分だけ外挿する
  - 外挿の上限（例: 0.25 秒）を設ける。メインスレッドが GC などで止まったときに、溜まっていた予約が一斉に鳴るのを防ぐ
  - 再生開始・停止・ループ直後にも書き込んで、値が古くならないようにする
- ワーカーが呼ぶ Godot の API は `AudioStreamPlaybackPolyphonic` の `PlayStream()` / `StopStream()` の 2 つだけにする
  - このクラスはオーディオスレッドとの競合には安全だが、**呼び出し元のスレッド同士の競合からは保護されていない**
  - メインスレッドからの呼び出しも含め、すべて同じロックの中で行う
- 何も予約されていないときは長めに sleep し、新しい予約が入ったら起こす（`ManualResetEventSlim` など）

### 発火のしきい値は出力レイテンシの分だけ前にする

`songTime` は「今聞こえている位置」なので、目標時刻に達した瞬間に `Play()` すると、実際に聞こえるのは出力レイテンシの分だけ遅れる。

```csharp
double FireThreshold() => clock.SongTime + clock.EffectiveOutputLatencySec + schedulerLeadSec;
```

`schedulerLeadSec` はポーリング間隔の半分にし、ポーリングによるずれの平均を 0 に寄せる。

### 先読みスケジューラの出力は、イベントキューに入れてから発火する

- 「現在から N 拍先までのイベントを返す」先読み型のスケジューラの戻り値を、そのまま `Play()` に渡すと、先読みした分だけ早く鳴る
- 戻り値はいったんイベントキューに入れ、時計が追いついたら取り出して発火する

```csharp
queue.Push(at, payload);                 // at は拍番号でも秒でもよい（軸は呼び出し側が決める）
foreach (var e in queue.Drain(current, maxAhead)) Fire(e);
```

- `Drain(current, maxAhead)` は、`maxAhead` より先の古いエントリを捨てる安全弁。ループの巻き戻し、シーク、曲の切り替えで残ったエントリを掃除する
- 先読みの幅を 0 にして回避しようとしない。スケジューラ側の追いつき処理とぶつかって拍が抜ける

### 音量のフェードも同じ考え方

`linearRampToValueAtTime()` に相当する API もない。エンベロープを純粋関数（Core）として書き、毎フレーム評価した値を `AudioStreamPlayer.VolumeLinear` に代入する。

## ループ再生

- ループの終端が曲の末尾なら、`AudioStreamOggVorbis.Loop` / `LoopOffset` を使う。サンプル単位で正確で、毎フレームの処理も要らない
- ループの終端を曲の途中にしたい場合は、Godot の ogg ストリームにはループ終端のプロパティがないので、`songTime` が終端に達したことを毎フレーム検出して `Seek()` で戻す。つなぎ目の音が気になるなら、クロスフェードを検討する
- ループの巻き戻しで、時計は 1 周分**戻る**。絶対的な `songTime` で記録したタイムスタンプ（「この時刻に消える」「この時刻に生まれた」など）は、そのままだと 1 周分未来になり、それを条件にしている処理が止まる
  - 巻き戻しの量を時計から通知し、ロジック系の各システムで `OnLoopWrap(shift)` を呼んで、全タイムスタンプから `shift` を**引く**（クリアはしない。ループをまたいだ処理を継続させるため）
  - **引いた結果を 0 で clamp しない。** 負の値は「描かない」「未発生」として自然に扱われる。clamp すると、とうに終わったイベントが全部「今」に揃い、一斉に再生される
  - 寿命 1〜2 秒の見た目だけのタイムスタンプは、ずらさなくても実害が小さい（一度だけフェードがおかしくなる程度）
  - **ゲームの進行を左右するタイムスタンプを新しく追加したら、最初から `OnLoopWrap()` の対象に入れる**

## 読み込み

- import 済みの `AudioStream` は `ResourceLoader.Load<AudioStream>()` で同期的に読める。SE はプレイヤーのコンストラクタでまとめて読み込む
- 短い SE を重ねて鳴らすなら、`AudioStreamPolyphonic` + `AudioStreamPlaybackPolyphonic.PlayStream()` を使う
- 外部の音声ファイルを ogg にする場合: Homebrew の ffmpeg には `libvorbis` が入っていないことがある。そのときは ffmpeg 内蔵の `vorbis` エンコーダを使う（`-c:a vorbis -strict -2`）
