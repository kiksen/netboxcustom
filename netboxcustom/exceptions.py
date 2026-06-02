from typing import Any


class NetboxCustomBase(Exception):
    def __init__(self, message: str, **kwargs: dict[str, Any]):

        self.message = message
        self.status_code: int = 500
        self.extra = kwargs
        self.status = "1"  # soll String sein!

    def __str__(self):
        result = f"{self.message} ({self.status_code})"
        if self.extra:
            extra_str = " ["
            for k, v in self.extra.items():
                extra_str += f"{k}={v} "
            extra_str = extra_str.rstrip()
            extra_str += "]"
            result += extra_str
        return result

    def as_dict(self) -> dict[str,Any]:
        result : dict[str,Any]= {
            "message": self.message,
            "status_code": self.status_code,
            "status": self.status,
        }
        result.update(self.extra)
        return result


class NetboxCustomCreateVirtualChassisError(NetboxCustomBase):
    def __init__(self, message: str, **kwargs):
        self.message = message
        super().__init__(f"{message}", **kwargs)
        self.status_code = 400


class NetboxCustomCreateDeviceError(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 400


class NetboxCustomLookupError(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


class NetboxCustomNotFoundError(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


class NetboxCustomFieldMissing(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 404


# used to consolidate all other errors
class NetboxCustomGeneralError(NetboxCustomBase):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"{message}")
        self.status_code = 400
        self.status_code = 400
        self.status_code = 400
