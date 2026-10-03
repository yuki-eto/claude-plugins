# ハマりどころ一覧

症状から引くための索引。詳しい説明は各章にある。

## 環境・ビルド

| 症状 | 原因 | 対処 | 章 |
|---|---|---|---|
| 「.NET assemblies not found」で落ちる / segfault | `godot` が symlink になっている | 実バイナリを `exec` するラッパースクリプトにする | [build](build-test-tooling.md) |
| clone 直後の `--import` が上と同じエラーで落ちる | C# を一度もビルドしていない | `dotnet build` を先に実行する（`run.sh` / `export.sh` で順序を固定する） | [build](build-test-tooling.md) |
| `dotnet build` が 5 分固まった後「0 エラー」で失敗する | サンドボックスが MSBuild のノード間 IPC を遮断している | `-m:1 -nodeReuse:false --disable-build-servers` を付ける | [build](build-test-tooling.md) |
| `dotnet test` が `SocketException (13)` で失敗する | vstest のループバック通信が遮断されている | `--no-build` を付け、単独のコマンドとしてサンドボックスを外して実行する | [build](build-test-tooling.md) |
| `godot` コマンドが出力なしで止まる | サンドボックス | 単独のコマンドとしてサンドボックスを外して実行する | [build](build-test-tooling.md) |
| アプリに `lib/` や `tools/` のコードが二重に入る / `Main` が重複する | SDK の既定の glob。`.gdignore` はエディタのスキャンしか止めない | `<Compile Remove="lib/**/*.cs" />` などを書く | [setup](project-setup.md) |
| csproj の SDK バージョンが勝手に変わり、`.csproj.old` ができる | エディタを上げると自動で書き換わる | 差分をコミットし、`.old` を消す | [setup](project-setup.md) |

## iOS / エクスポート

| 症状 | 原因 | 対処 | 章 |
|---|---|---|---|
| エディタを上げたら、全 preset のエクスポートが失敗する | export templates は自動では入らない | テンプレートを展開する。`export.sh` で事前に確認する | [ios](native-ios.md) |
| iOS の起動直後にクラッシュする（`GlobalizationNative_LoadICUData`） | ICU のデータが同梱されない | `InvariantGlobalization=true` | [setup](project-setup.md) |
| iOS でだけ JSON の読み込みが壊れる | reflection ベースの JSON が trim で消える | source generation の `JsonSerializerContext` を使う | [runtime](runtime-architecture.md) |
| 縦向きのつもりが iOS で横向きになる | orientation に文字列を書いた（Godot 3 の書式） | 整数の enum で書く | [setup](project-setup.md) |
| Xcode で自動署名がオフ、Team が None になっている | Godot の生成物で `CODE_SIGN_STYLE = "Manual"` になる | `export.sh` で pbxproj をパッチする | [ios](native-ios.md) |
| パッチした署名設定が数分後に元に戻る | 開いたままの Xcode が古い pbxproj を書き戻す | エクスポートの前に Xcode を閉じる | [ios](native-ios.md) |
| Release の Signing に「conflicting provisioning settings」と出る | Personal Team と Distribution の署名 ID が矛盾している | debug には影響しない。有料メンバーシップに入ってから対処する | [ios](native-ios.md) |
| 「target folder doesn't exist」でエクスポートが失敗する | Godot は出力先を作らない | 事前に `mkdir -p` する | [build](build-test-tooling.md) |
| `xcodebuild` が exit 70 で失敗する | 端末がロックされている | `generic/platform=iOS` でビルドする | [ios](native-ios.md) |

## UI・入力

| 症状 | 原因 | 対処 | 章 |
|---|---|---|---|
| 縦横比の違う端末で上下や左右に黒帯が出る | `aspect="keep"` | `expand` にし、`UiFrame` で収める | [ui](ui-input-mobile.md) |
| デスクトップで画面を広げると UI が崩れる | viewport に対する比率とピクセル値を混ぜている | 固定のデザイン空間（`UiFrame`）で組む | [ui](ui-input-mobile.md) |
| モーダルだけ二重に縮尺される | ホスト画面のフレームの下にモーダルを入れた | モーダルに専用のフレームを持たせ、ホストのルートに追加する | [ui](ui-input-mobile.md) |
| 下の方のボタンがホームインジケーターに重なる | セーフエリアを考慮していない | `SafeArea.InViewport()` の中に UI を収める | [ui](ui-input-mobile.md) |
| iOS で起動直後だけセーフエリアがずれる | インセットが後から通知される | 毎フレーム値を比較し、変化をイベントで知らせる | [ui](ui-input-mobile.md) |
| `Show()` したのに何も表示されない | アンカーで決めたサイズが `(0,0)` に戻される | ルートの Control では `FitToViewport()` で明示的にサイズを決める | [ui](ui-input-mobile.md) |
| Tab でモーダルの外のボタンが押せてしまう | フォーカスが有効 | 全 Control を `FocusMode = None` にする | [ui](ui-input-mobile.md) |
| 1 回のタップで処理が 2 回走る / 音は鳴るのに見た目が反応しない | タッチとマウスのイベントが両方届いている | `InputEventScreenTouch { Pressed: true, Index: 0 }` だけを受け付ける | [ui](ui-input-mobile.md) |
| モーダルの背景をタップすると背後のボタンも押される | 押した瞬間に閉じている | 離したときに閉じる | [ui](ui-input-mobile.md) |
| リンクが 2 回開く | `LinkButton.Uri` と `Pressed` ハンドラの両方で開いている | `Uri` だけにする | [ui](ui-input-mobile.md) |
| 縮尺した画面で文字がぼやける | MSDF でない動的フォント | MSDF で import する | [ui](ui-input-mobile.md) |
| span を取る描画 API で「`Vector2[]` に変換できない」と出る | 省略可能引数を省いたため、span のオーバーロードが候補から外れた | 全引数を明示する | [ui](ui-input-mobile.md) |
| 「Invalid polygon data, triangulation failed」 | 退化した多角形 | 面積を調べ、ほぼ 0 なら描かない | [ui](ui-input-mobile.md) |
| 図形が多いと CPU で詰まる（特にモバイル） | ネイティブ呼び出しの回数が多すぎる | 三角形・線をまとめて一括で描く | [ui](ui-input-mobile.md) |

## オーディオ・タイミング

| 症状 | 原因 | 対処 | 章 |
|---|---|---|---|
| グリッドにスナップした SE がときどき二重に鳴る | 時計の値が同じフレーム内で後戻りする | 1 フレームに 1 回だけ計算し、後戻りを無視するフィルタを通す | [audio](audio-timing.md) |
| 拍に合わせた SE が少し遅れて聞こえる | 目標時刻ちょうどに `Play()` している | 出力レイテンシの分だけ前に発火する | [audio](audio-timing.md) |
| 60fps のときだけリズムがもたつく | フレーム単位のポーリングによるずれ | 専用スレッドで 1ms ごとにポーリングする | [audio](audio-timing.md) |
| 先読みした拍のクリック音が早く鳴る | 先読みの結果をそのまま再生している | イベントキューに入れ、時刻が来てから発火する | [audio](audio-timing.md) |
| ワーカースレッドからの再生でまれに異常が起きる | `AudioStreamPlaybackPolyphonic` は呼び出しスレッド同士の競合から保護されていない | すべての呼び出しを同じロックで直列化する | [audio](audio-timing.md) |
| ループの継ぎ目を越えると処理が止まる | 絶対時刻のタイムスタンプが 1 周分未来になる | `OnLoopWrap(shift)` で全タイムスタンプをずらす | [audio](audio-timing.md) |
| ループの継ぎ目で過去の演出が一斉に再生される | ずらしたタイムスタンプを 0 で clamp した | clamp せず負の値のままにする | [audio](audio-timing.md) |
| iOS でレイテンシの補正が効かない | `GetOutputLatency()` が 0 を返す | プロジェクト設定の値をフォールバックに使う | [audio](audio-timing.md) |
