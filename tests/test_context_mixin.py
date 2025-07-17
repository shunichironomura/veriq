from veriq._utils import ContextMixin


class TestContextMixin(ContextMixin):
    def __init__(self, name: str) -> None:
        self.name = name


class TestContextMixin2(ContextMixin):
    def __init__(self, name: str) -> None:
        self.name = name


def test_current() -> None:
    """Test that the current context can be retrieved."""
    with TestContextMixin("test") as ctx:
        current = TestContextMixin.current()
        assert current is ctx


def test_nested() -> None:
    """Test that nested contexts work correctly."""
    with TestContextMixin("outer") as outer_ctx:
        current_outer = TestContextMixin.current()
        assert current_outer is not None
        assert current_outer is outer_ctx

        with TestContextMixin2("inner") as inner_ctx:
            current_inner = TestContextMixin2.current()
            assert current_inner is not None
            assert current_inner is inner_ctx

            current_outer = TestContextMixin.current()
            assert current_outer is not None
            assert current_outer is outer_ctx

        current_outer = TestContextMixin.current()
        assert current_outer is not None
        assert current_outer is outer_ctx
