# 登录态目录(cookies / storage_state)

本目录存放各平台的 Playwright 登录态文件(如 `toutiao_state.json`),供 autowz 无人值守发布使用。

- **这些文件含登录凭证,绝不入库**(已在根 `.gitignore` 排除 `*_state.json` / `*.json`)。
- 生成方式:在本地电脑运行 `python scripts/login_helper.py <平台>`,扫码登录后导出,再传到本目录。
- 登录态过期(通常数周)后重新导出覆盖即可。
