class WechatAPIError(Exception):
    """微信 API 返回错误。"""

    def __init__(self, errcode: int, errmsg: str) -> None:
        self.errcode = errcode
        self.errmsg = errmsg
        super().__init__(f"微信 API 错误 [{errcode}]: {errmsg}")
