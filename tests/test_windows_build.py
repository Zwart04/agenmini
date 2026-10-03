import io
from windows import build


def test_ci_token_used_only_for_github_api_without_redirects(monkeypatch):
    monkeypatch.setenv('GH_TOKEN','private-ci-token')
    seen=[]
    def open_url(request,**kw):
        seen.append(request)
        return io.BytesIO(b'{}')
    class Opener:
        open=staticmethod(open_url)
    def make_opener(handler):
        assert handler.redirect_request(None,None,302,'',{},'https://untrusted.example') is None
        return Opener()
    monkeypatch.setattr(build.urllib.request,'build_opener',make_opener)
    monkeypatch.setattr(build.urllib.request,'urlopen',open_url)
    build.get('https://api.github.com/repos/git-for-windows/git/releases/latest')
    build.get('https://github.com/git-for-windows/git/releases/download/version/MinGit.zip')
    build.get('https://nodejs.org/dist/SHASUMS256.txt')
    assert seen[0].get_header('Authorization')=='Bearer private-ci-token'
    assert all(r.get_header('Authorization') is None for r in seen[1:])
