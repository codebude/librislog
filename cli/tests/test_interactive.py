from llc._interactive import select_from_list


class TestSelectFromList:
    def test_returns_selected_item(self, mocker):
        mocker.patch("questionary.select", return_value=mocker.MagicMock(ask=lambda: "bar"))
        items = ["foo", "bar", "baz"]
        result = select_from_list(items)
        assert result == "bar"

    def test_returns_none_on_empty_list(self, mocker):
        result = select_from_list([])
        assert result is None

    def test_returns_none_on_cancel(self, mocker):
        mocker.patch("questionary.select", return_value=mocker.MagicMock(ask=lambda: None))
        result = select_from_list(["foo", "bar"])
        assert result is None
