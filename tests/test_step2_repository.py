import pytest

from app.services.step2_repository import save_step2_fusion_result


def test_save_step2_fusion_result_not_yet_implemented():
    with pytest.raises(NotImplementedError):
        save_step2_fusion_result(user_id="user-1", date="2026-08-11", result=None)
