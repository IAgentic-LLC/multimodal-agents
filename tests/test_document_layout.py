from multimodal_agents.run_document_layout import parse_xhtml


def test_layout_parser_preserves_table_figure_and_caption_relation():
    content = """<html><body><h1>Report</h1>
    <table><tr><td>Service</td><td>Error</td></tr></table>
    <p class="captioned_Figure"><img src="embedded:chart.png"></p>
    <p class="image_Caption">Error-rate chart.</p>
    <div class="package-entry"><h1>chart.png</h1></div>
    </body></html>"""
    result = parse_xhtml(content)["structured"]
    assert result["heading_count"] == 1
    assert result["table_rows"] == [["Service", "Error"]]
    assert result["figure"]["caption"] == "Error-rate chart."
    assert result["relationships"][0]["type"] == "caption_of"
