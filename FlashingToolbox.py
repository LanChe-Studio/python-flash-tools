from Tool import MTKClientTool
from Tool import PlatformTools

class FlashingToolbox:
    def __init__(self, platform_tools: PlatformTools, mtk_client: MTKClientTool):
        self.platform_tools = platform_tools
        self.mtk_client = mtk_client
        if not self.platform_tools.change_path_to_available():
            self.platform_tools = None
        if not self.mtk_client.change_path_to_available():
            self.mtk_client = None

