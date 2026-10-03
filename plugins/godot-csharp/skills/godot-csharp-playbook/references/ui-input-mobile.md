# UI・入力・モバイル対応

## 解像度と縦横比

### 方針

- `stretch/mode="canvas_items"` と `aspect="expand"` を組み合わせ、**viewport を端末の画面全体に広げる**（黒帯を出さない）
- その代わり viewport の縦横比は端末ごとに変わるので、**UI は固定サイズのデザイン空間（例: 540x960）で組み、その空間を丸ごと縮尺して収める**
- viewport に対する比率でのアンカー指定と、手で決めたピクセル値を混ぜない。混ぜると、基準と違う縦横比の画面で崩れる（実際に全画面で崩れた）

### UiFrame パターン

デザイン空間を safe area に aspect-fit させる `Control`。

```csharp
public partial class UiFrame : Control
{
    public static readonly Vector2 DesignSize = new(540, 960);

    private GameApp _app = null!;

    // GameApp.SafeAreaChanged は素の C# event なので、ノードが解放されても自動では外れない
    public override void _EnterTree()
    {
        _app = GetNode<GameApp>("/root/GameApp");
        GetViewport().SizeChanged += Refit;
        _app.SafeAreaChanged += Refit;
    }

    public override void _ExitTree()
    {
        GetViewport().SizeChanged -= Refit;
        _app.SafeAreaChanged -= Refit;
    }

    public override void _Ready()
    {
        MouseFilter = MouseFilterEnum.Ignore;
        Size = DesignSize; // 以降は Size を変えない
        Refit();
    }

    public void Refit()
    {
        Rect2 safe = SafeArea.InViewport(GetViewport());
        if (safe.Size.X <= 0 || safe.Size.Y <= 0) return;
        float fit = Mathf.Min(safe.Size.X / DesignSize.X, safe.Size.Y / DesignSize.Y);
        Scale = new Vector2(fit, fit);
        Position = safe.Position + (safe.Size - DesignSize * fit) / 2f;
    }
}
```

画面の組み方:

1. 画面のルートに、viewport 全体を覆う背景・スクリム（`SetAnchorsPreset(FullRect)`）を**フレームの外に**置く。こうすると余白やインセットの部分も覆える
2. その上に `UiFrame` を 1 つ置き、**中身はすべてその下に**入れる。アンカーもピクセル値も 540x960 の空間で解決される
3. モーダルは**自分専用の `UiFrame`** を持ち、ホスト画面のルートに追加する。ホストのフレームの下に入れると二重に縮尺される
4. `UiFrame` 自身には `SetAnchorsPreset()` を呼ばない（下の「Control のサイズ」を参照）

横画面用の画面を作るときは、デザイン空間を 960x540 に転置したフレームを使う。

### ゲームのフィールド（プレイ領域）

- フィールドも同じ縮尺係数 `min(vp.X / W, vp.Y / H)` を使う。ただしデザイン空間を `viewport / fit` とし、**基準の 540x960 を含む端末サイズの空間**にする（9:19.5 の端末なら 540x1170）。こうすると黒帯なしで画面全体を使える
- 位置の計算に使う定数（画面の幅・高さ）は直接読まず、実際の境界（`Bounds`）を各システムに渡す
- 極端な縦横比で破綻しないよう、最小・最大の縦横比で clamp し、範囲外はレターボックスにする
- トレードオフとして、端末によってプレイ領域の広さが変わる（密度を面積で補正するかはゲームごとに判断する）

### デスクトップのウィンドウ

- 起動時に `DisplayServer.ScreenGetUsableRect()` から、使える領域に収まる最大の 9:16 の矩形を計算し、そのサイズにする。タイトルバーの分は `WindowGetSizeWithDecorations() - WindowGetSize()` で差し引く
- その後は `WindowFlags.ResizeDisabled` で固定する。プレイ中にプレイ領域の形が変わるのを防ぐため
- サイズを変える場合（設定画面など）は、一時的に `ResizeDisabled` を外して `WindowSetSize()` し、また固定する（固定されたままだと `WindowSetSize()` が効かない）
- `SizeChanged` のたびにウィンドウの形を直すハンドラは、見た目がちらつくので使わない（試して戻した）
- 全画面表示は、横長になるとプレイ領域の形が変わるので慎重に扱う

## セーフエリア

```csharp
public static Rect2 InViewport(Viewport viewport)
{
    Rect2 full = viewport.GetVisibleRect();
    if (!OS.HasFeature("mobile")) return full;          // デスクトップでは使わない
    Rect2I safePx = DisplayServer.GetDisplaySafeArea();
    Vector2I windowPx = DisplayServer.WindowGetSize();
    if (safePx.Size.X <= 0 || safePx.Size.Y <= 0 || windowPx.X <= 0 || windowPx.Y <= 0) return full;
    var k = new Vector2(full.Size.X / windowPx.X, full.Size.Y / windowPx.Y);
    var safe = new Rect2((Vector2)safePx.Position * k, (Vector2)safePx.Size * k);
    Rect2 clipped = safe.Intersection(full);
    return clipped.Size.X <= 0 || clipped.Size.Y <= 0 ? full : clipped;
}
```

- **モバイルでだけ使う。** デスクトップでは `GetDisplaySafeArea()` が「画面」の矩形を返し、ウィンドウのクライアント領域とは無関係になる
- 描画（背景・フィールド）は画面全体に広げ、**読む・タップする UI だけ**をセーフエリアの中に収める
- iOS は、ウィンドウが最終サイズになった**後から**インセットを通知・変更することがある。`Viewport.SizeChanged` だけでは拾えないので、`GameApp._Process()` で毎フレーム `GetDisplaySafeArea()` を比較し、変化したら `SafeAreaChanged` イベントを発火する

## Control のサイズ（後から表示する Control が 0x0 になる）

- 最初は `Visible = false` で、後から `Show()` する Control が、`SetAnchorsPreset()` でサイズを決めていると `(0,0)` のまま固まることがある。`Show()` は効いているのに何も描かれない
- 親が `CanvasLayer` のときに限らず、普通の Control の下でも起きる
- 左右（上下）で異なるアンカーを設定すると、レイアウトのたびに手で入れた `Size` が上書きされる（Godot のログに「Nodes with non-equal opposite anchors will have their size overridden after _ready()」と出る）
- 対処: そのような**ルートの Control には `SetAnchorsPreset()` を使わず**、`Position` / `Size` を明示的に設定する拡張メソッドだけでサイズを決める。`_Ready()` と `SizeChanged` で呼ぶ。子は普通にアンカーを使ってよい

```csharp
public static void FitToViewport(this Control control)
{
    control.Position = Vector2.Zero;
    control.Size = control.GetViewportRect().Size;
}
```

## フォーカス

- ポインタ操作だけのゲームなら、**すべての Control を `FocusMode = None` にする。** `Button` / `HSlider` / `ScrollContainer` / `LinkButton` を生成するヘルパーの中で `DisableFocus()` を呼ぶ
- フォーカスが生きていると、Tab でモーダルの外のボタンにフォーカスが移り、モーダルが二重に開くなどの不具合が起きる。フォーカスのループを作って閉じ込める方式は試したが、フォーカスを切る方が単純で確実だった
- 例外は文字入力の `LineEdit`。フォーカスが無いと入力できず、iOS の仮想キーボードも出ない
  - `FocusMode = Click` にする（`All` にはしない。Tab での移動先候補になるのは `All` だけ）
  - Enter、入力欄の外へのタップ、各ボタンのハンドラの先頭（モーダルを出す前）で `ReleaseFocus()` を呼ぶ

## タップ入力

### 受け付けるイベントは 1 種類にする

- `emulate_touch_from_mouse=true`（デスクトップ）と、既定で有効な `emulate_mouse_from_touch`（端末）のせいで、**1 回のタップで実イベントと合成イベントの両方が届く**
- 両方に反応するハンドラは 1 回のタップで 2 回動く（実例: 1 回目で発動した処理を、2 回目が「既に動作中」と判定して止めてしまい、音だけ鳴って画面上は何も起きなかった）
- **`InputEventScreenTouch { Pressed: true, Index: 0 }` だけを受け付ける。** `emulate_touch_from_mouse` が有効なので、デスクトップのクリックでもこれが届く

### モーダルの背景は「離したとき」に閉じる

- 押した瞬間にモーダルを閉じると、同じタップの続きのイベントで GUI の当たり判定がやり直され、背後にあったボタンが押下状態になり、指を離したときに発火する
- 背景は押している間ずっと `MouseFilter = Stop` で入力を止め、**同じ背景で押されて離されたとき**にだけ閉じる

```csharp
public static void WireBackdropDismiss(Control backdrop, Action onDismiss)
{
    backdrop.MouseFilter = Control.MouseFilterEnum.Stop;
    bool pressed = false;
    backdrop.GuiInput += e =>
    {
        if (e is InputEventScreenTouch { Index: 0 } t)
        {
            if (t.Pressed) pressed = true;
            else if (pressed) { pressed = false; onDismiss(); }
        }
    };
}
```

### LinkButton

`LinkButton.Uri` を設定すると、押したときに内部で `OS.ShellOpen()` が呼ばれる。さらに `Pressed` ハンドラで `ShellOpen()` を呼ぶと、リンクが 2 回開く。

## フォント

- **フォントは MSDF で import する**（`.ttf.import` に `multichannel_signed_distance_field=true`）。追加するフォントもすべて同じにする
- 縮尺された CanvasItem（`UiFrame` やフィールドのルート）の下では、MSDF でないフォントは縮尺前の解像度でラスタライズされ、GPU で拡大されてぼやける
- Godot 4.5 以降の oversampling の設定（`CanvasItem.OversamplingWithScale`）では、同じツリーの中でくっきりする Label とぼやける Label が混在し、安定しなかった。MSDF ならこの仕組み自体を通らない
- MSDF の注意点: ヒンティングが効かないので極小の文字はやや柔らかくなる。輪郭が重なったグリフは崩れる（Google Fonts から変換したフォントに多い）。追加するときに確認する
- 可変フォントの太さ・等幅数字は、`FontVariation` を作るヘルパーにまとめる

## 描画

- 図形を大量に描く層は `Node2D._Draw()` で毎フレーム描き直す（イミディエイトモード）。それで十分に速い
- **ただし 1 図形ごとにネイティブ呼び出しをしない。** 三角形や線をフレーム単位のバッファに溜め、最後に `RenderingServer.CanvasItemAddTriangleArray()` 1 回と、線幅ごとの `DrawMultilineColors()` でまとめて出す。実例では 1 フレームあたり約 5000 回のネイティブ呼び出しがボトルネックになっていた（iPad で計測）
- 加算合成なら描く順序が結果に影響しないので、まとめて出しても見た目は変わらない。ブレンドモードは描画呼び出しごとには指定できないので、ノード全体に `CanvasItemMaterial { BlendMode = Add }` を設定する
- **`ReadOnlySpan<T>` を取るオーバーロードで省略可能引数を省くと、そのオーバーロードが候補から外れる**（「`Vector2[]` に変換できない」という見当違いのエラーになる）。`DrawColoredPolygon(points, fill, ReadOnlySpan<Vector2>.Empty, null)` のように全引数を書く
- 計算で作った多角形は、`DrawColoredPolygon()` の前に面積（shoelace 公式）を調べ、ほぼ 0 なら描かない。退化した多角形を渡すと「triangulation failed」というネイティブのエラーになり、C# の例外としては捕まえられない
