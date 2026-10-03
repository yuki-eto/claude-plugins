# ネイティブ連携と iOS / macOS 配布

## ネイティブ連携

### 置き場所

- **OS の API を直接呼ぶ P/Invoke**（`DllImport` で AudioToolbox を呼ぶ、ObjC runtime 経由で `UIDocumentPickerViewController` を出す、など）は `MyGame.Native` に置く。Godot にも Core にも依存させない
- **.NET 以外の言語で書くネイティブコード**（Swift など）は `godot/native/<Name>/` に置き、`.gdignore` を置く。ビルド成果物は gitignore した `godot/native/bin/` に出す
- 対応していないプラットフォームでは `PlatformNotSupportedException` を投げるファクトリにし、呼び出し側でフォールバックする

### 必須ではないネイティブライブラリは、実行時に探して読み込む

- 存在しないかもしれないパスを `DllImport` で直接指定しない
- 候補パスの一覧を Godot 側で作り（Godot の API が必要なため）、Native 側で `NativeLibrary.TryLoad` を順に試す
- 関数ポインタは `NativeLibrary.TryGetExport` で取り出し、`delegate* unmanaged[Cdecl]<...>` にキャストする。`Marshal.GetDelegateForFunctionPointer` は使わない（AOT に対応しやすくするため）
- 読み込みは `Lazy<T>` で 1 回だけ行い、失敗した理由をログに残す。理由が分かるので、黙ってフォールバックしても後から追える

```csharp
// App 側: 候補パス（開発時 → macOS エクスポート → iOS の順）
IEnumerable<string> CandidatePaths()
{
    if (OperatingSystem.IsMacOS() && !OS.HasFeature("template"))   // エディタ / run.sh で起動したとき
        yield return ProjectSettings.GlobalizePath("res://native/bin/macos/libFoo.dylib");
    string exeDir = Path.GetDirectoryName(OS.GetExecutablePath()) ?? "";
    if (OperatingSystem.IsMacOS())
        yield return Path.GetFullPath(Path.Combine(exeDir, "..", "Frameworks", "libFoo.dylib"));
    if (OperatingSystem.IsIOS())
    {
        yield return Path.Combine(exeDir, "Frameworks", "Foo.framework", "Foo");
        yield return "@rpath/Foo.framework/Foo";
    }
}
```

- 呼び出しは try/catch で囲み、失敗したら C# の実装にフォールバックする。**ネイティブ機能は「あれば使う」ものであり、必須の依存にしない**
- `run.sh` / `export.sh` の中でネイティブのビルドが失敗しても、警告を出すだけで先に進める

### Swift ブリッジ

- Swift から `@_cdecl("foo_xxx")` で C ABI の関数を公開する。最低限、次の 3 つを用意する
  - 利用できるかどうかを返す関数（`foo_is_available() -> Int32`。`#available` で判定する）
  - 本体の処理（結果は JSON などの文字列で返す）
  - 返した文字列を解放する関数（`foo_free`）。Swift 側で確保したメモリは Swift 側で解放させる
- Swift の async API は、C の入口でブロッキング呼び出しに包む（セマフォと結果を入れる箱を使う）
- ビルドは SwiftPM ではなく `xcrun swiftc` を直接呼ぶ。SwiftPM では低いデプロイメントターゲットを指定できないことがある
  - macOS: `-emit-library`、`-install_name @rpath/libFoo.dylib`
  - iOS: `.framework` の形に組み立て、`Info.plist` を書いて `plutil -convert binary1` で変換する
- **新しい OS にしか無いフレームワークは weak link にし、デプロイメントターゲットは低くする。** 古い OS でもライブラリ自体は読み込め、「利用できない」と返すだけにするため
  - ビルド後に `otool -l` で `LC_LOAD_WEAK_DYLIB` になっているか確認する。なっていなければ `-Xlinker -weak_framework -Xlinker <Name>` を付けて再ビルドする
- 成果物は同じボリューム上の一時ディレクトリでビルドしてから `mv` する（アトミックに置き換えるため）。ソースとスクリプトより新しければビルドを飛ばす

### エクスポートへの同梱

- **macOS**: `.app/Contents/Frameworks/` に dylib をコピーし、`codesign --force --sign -` で署名する。`.app` に既に署名があれば、`--preserve-metadata=entitlements` を付けて `.app` ごと署名し直す
- **iOS**: Godot の `.gdip` プラグインは動的フレームワークをそのまま埋め込めない（static lib と init/deinit 関数が必要）。そこで、生成された `project.pbxproj` の既存の「Embed Frameworks」フェーズに、`PBXFileReference` と `PBXBuildFile`（`CodeSignOnCopy`）を追記する
  - リンクはせず、埋め込むだけにする（実行時に `dlopen` するため）
  - 追記した後は ID の出現回数と `plutil -lint` で検証する。想定どおりでなければ「再エクスポートせよ」と言って失敗させる
  - Godot の iOS テンプレートの構造が変わったら、警告を出して同梱せずに続行する

## iOS エクスポート

### 準備

- **export templates はエディタとは別に入れる必要がある。** `Godot_v<ver>-stable_mono_export_templates.tpz` を `~/Library/Application Support/Godot/export_templates/<ver>.stable.mono/` に展開する
  - エディタを上げるたびに全 preset のエクスポートが壊れる（実例では 2 日間気付かなかった）
  - `export.sh` で `godot --version` から期待されるディレクトリ名を作り、ビルドの前に存在を確認する（[templates/export.sh](../templates/export.sh)）
- `xcode-select` で、Command Line Tools ではなく Xcode.app 本体を指しておく
- `export_presets.cfg` の iOS preset
  - `application/export_project_only=true`: Xcode プロジェクトだけを出力し、ビルドは `xcodebuild` で行う
  - `application/app_store_team_id`: Team ID
  - `application/bundle_identifier`
  - `application/targeted_device_family`: `2` は iPhone + iPad

### 署名まわりの既知の問題（Godot 4.7 時点）

- **生成された `project.pbxproj` で、ターゲットごとの `CODE_SIGN_STYLE` が必ず `"Manual"` になる。** その結果、Xcode では「Automatically manage signing」がオフ、Team が None で開く
  - 古い `TargetAttributes` のほうは `ProvisioningStyle = Automatic` と Team ID が正しく入っていて、2 つの設定が食い違っている
  - `export_presets.cfg` の設定では直せないので、`export.sh` で毎回パッチする
    - `CODE_SIGN_STYLE = Automatic;` にする
    - `DEVELOPMENT_TEAM = <TEAM_ID>;` にする
    - 空の `PROVISIONING_PROFILE` / `PROVISIONING_PROFILE_SPECIFIER` の行を消す
    - 書き換えた後、Debug と Release の 2 箇所に入ったか回数で確認する
  - Xcode の Signing の画面で手で直さない（再エクスポートで消える）
- **`export.sh` を実行するときは Xcode を閉じておく。** 古いプロジェクトを開いたままだと、数分後に Xcode がメモリ上の古い `project.pbxproj` を書き戻し、パッチが消える。開いているかどうかはスクリプトから確実には判定できないので、`pgrep -x Xcode` で警告だけ出す
- 無料の Personal Team では `Apple Development` しか発行できない。そのため Release 構成の `CODE_SIGN_IDENTITY = "iPhone Distribution"` と矛盾し、Xcode に「conflicting provisioning settings」と表示される。debug ビルドには影響しない。有料メンバーシップに入ったら、Release の署名 ID を `export.sh` でパッチするかを決める（`export_presets.cfg` 側を変えると、Godot が `CODE_SIGN_STYLE` を `Manual` にしてしまう）

### 向き（orientation）の確認

`project.godot` の orientation を整数で書き損ねると、plist が何も言われずに横向きになる（[project-setup.md](project-setup.md)）。`export.sh` で、生成された `<Name>-Info.plist` に必要な向き（`UIInterfaceOrientationPortrait` など）が入っているか `grep` で確認し、無ければ失敗させる。生成された plist を手で直さない。

### シミュレーター

C#/NativeAOT のシミュレーター向けビルドには、x64 と arm64 の制約がある。きれいに失敗したならそれ自体が有益な結果なので、深追いしない。

## 実機への配布（debug）

```bash
godot/tools/export.sh iOS debug
```

```bash
xcodebuild -project godot/build/ios/MyGame.xcodeproj -scheme MyGame -configuration Debug \
  -destination 'id=<DEVICE_UDID>' -derivedDataPath <scratch>/dd-ios -allowProvisioningUpdates \
  DEVELOPMENT_TEAM=<TEAM_ID> CODE_SIGN_STYLE=Automatic PRODUCT_BUNDLE_IDENTIFIER=com.example.mygame build
```

```bash
xcrun devicectl device install app --device <DEVICECTL_ID> <scratch>/dd-ios/Build/Products/Debug-iphoneos/MyGame.app
```

- UDID は `xcrun xctrace list devices`、devicectl 用の ID は `xcrun devicectl list devices` で調べる
- 端末がロックされていると `xcodebuild -destination 'id=...'` が exit 70 で失敗する。その場合は `-destination 'generic/platform=iOS'` でビルドする（出力先は同じ）
- `devicectl install` が `CoreDeviceError 10003`（ロック中）や `12040`（DDI のマウント）で失敗したら、端末のロックを解除してもらって再試行する。`CoreDeviceError 4000` や `IXRemoteErrorDomain error 5` は一時的なエラーなので、3 回程度まで再試行する
- ネイティブのフレームワークを同梱しているなら、`.app/Frameworks/<Name>.framework` があることを確認する
- 空の `NSCamera` / `NSPhotoLibrary` / `NSMicrophone` の usage description についての警告は、debug ビルドでは無害
- 実機へのインストールまでがエージェントの担当で、起動して確認するのは人間
