"""Errors raised by services. They carry plain-language messages so the
same text can be shown on the website or read back by a chatbot."""


class ServiceError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    status_code = 404


class AuthError(ServiceError):
    status_code = 401


class ConflictError(ServiceError):
    status_code = 409
