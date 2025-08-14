from model.ztMicroscope import ZtBaseMicroscope
from model.ztObject import ZtObject


class ZtStemStrategies:
    def __init__(self, **kwargs):
        self._microscope = kwargs.get('microscope', None)
        self._object = kwargs.get('object', None)

    @property
    def microscope(self) -> ZtBaseMicroscope:
        return self._microscope

    @microscope.setter
    def microscope(self, val) -> None:
        # setter for microsocpe
        self._microscope = val

    @property
    def object(self) -> ZtObject:
        return self._object

    @object.setter
    def object(self, val) -> None:
        self._object = val

    def run(self, *args, **kwargs) -> None:
        #ZtStemStrategies 入口
        pass


