import sys,json
import pytest
from backend.storage import ServiceError
from backend.services.source_monitor import SourceMonitor
from backend.monitor import main
from backend.tests.local_temp import LocalTemporaryDirectory

@pytest.mark.parametrize('code',['SOURCE_CHECK_NOT_DUE','SOURCE_CHECK_IN_PROGRESS'])
def test_monitor_cli_defers_normal_scheduler_conflicts_without_traceback(monkeypatch,capsys,code):
    directory=LocalTemporaryDirectory()
    try:
        monkeypatch.setattr(sys,'argv',['monitor','--check','nta-jee-main','--data-dir',directory.name])
        def deferred(*args,**kwargs):raise ServiceError(429,code,'Scheduled source check is protected')
        monkeypatch.setattr(SourceMonitor,'check',deferred)
        main()
        output=capsys.readouterr()
        assert json.loads(output.out)['status']=='DEFERRED'
        assert json.loads(output.out)['code']==code and not output.err
    finally:directory.cleanup()
