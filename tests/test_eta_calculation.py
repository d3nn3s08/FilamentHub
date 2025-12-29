from app.services.job_tracking_service import JobTrackingService
from app.models.spool import Spool


def test_calc_usage_basic():
    svc = JobTrackingService()
    # Spool with known full/empty weights
    spool = Spool(material_id="m1", weight_full=1000.0, weight_empty=200.0)

    used_mm, used_g = svc._calc_usage(spool, start_remain=100.0, end_remain=90.0, start_total_len=10000)

    # 10% of 10000 mm -> 1000 mm
    assert abs(used_mm - 1000.0) < 1e-6
    # 10% of weight difference (800g) -> 80g
    assert abs(used_g - 80.0) < 1e-6

