import numpy as np
from zhoutomo_client.models.ztImage import ZtImage
from zhoutomo_client.processing.legacy.utils import get_definition


class ZtDefinitionEvaluator:
    def __init__(self, image_input: np.ndarray = None, definition_evaluation_strategy: str = 'VGR'):
        self._image_input: np.ndarray = image_input  # 用于去噪的输入图像，为 ZtImage 对象
        self._definition_evaluation_strategy: str = definition_evaluation_strategy  # 清晰度评价的方法

    def evaluate(self):
        image_definition, _ = get_definition(self._image_input, method=self._definition_evaluation_strategy)
        return image_definition
