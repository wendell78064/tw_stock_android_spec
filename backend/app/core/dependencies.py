from fastapi import Request

from app.services.readiness import ReadinessChecker


def readiness_checker(request: Request) -> ReadinessChecker:
    return request.app.state.readiness_checker

