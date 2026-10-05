"""Adapt prompt_toolkit to redirected Windows stdio; run the unmodified upstream CLI."""
if __name__=='__main__':
    import runpy
    from prompt_toolkit.application import create_app_session
    from prompt_toolkit.input import DummyInput
    from prompt_toolkit.output import DummyOutput
    with create_app_session(input=DummyInput(),output=DummyOutput()):
        runpy.run_module('minisweagent.run.mini',run_name='__main__')
