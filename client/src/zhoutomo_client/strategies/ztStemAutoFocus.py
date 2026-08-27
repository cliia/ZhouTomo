from typing import Optional

import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from zhoutomo_client.strategies.ztDefinitionEvaluator import ZtDefinitionEvaluator
from zhoutomo_client.strategies.ztDenoiser import ZtDenoiser
from zhoutomo_client.strategies.ztStemStrategy import ZtStemStrategies
from zhoutomo_client.models.ztMicroscope import ZtBaseMicroscope
from zhoutomo_client.models.ztObject import ZtObject
from zhoutomo_client.models.ztImage import ZtImage
from zhoutomo_client.processing.legacy.utils import is_monotonic, imrescale
from zhoutomo_client.processing.legacy.normxcorr2 import extract_pattern
from ztthread import ZtControlThread


class ZtStemAutoFocus(ZtStemStrategies):
    """
    ## `ZtStemAutoFocus(self, ztMicroscope, ztObject, **kwargs)`

    该策略的基本算法如下：

    1. **输入检查**：检查 `ztObject` 和 `ztMicroscope` 是否为已经注册，如果没有注册，返回错误。
    2. **进行自动聚焦**：使用自动聚焦算法进行自动聚焦。
    3. **输出结果**：`0` 代表正常结束，当前 `ztMicroscope` 的状态即为自动聚焦的结果；`1` 代表发生 Runtime 错误。

    ### 参数 Parameters

    * `ztMicroscope`：电镜对象
    * `ztObject`：目标样品对象
    * `center_strategy='xcorr2'`：归中方法，默认为互相关函数
    * `denoise_strategy='bm3d'`：去噪方法，默认为 `'bm3d'`，可选方法为 `'none'，`'gauss'`
    * `opt_strategy='gd'`：最优化方法，默认为 `'gd'`
    * `opt_strategy_kwargs={'Iteration':10, 'Alpha':1}`：
    * `definition_evaluation_strategy='VGR'`：图像清晰度评价方法，默认为 `'VGR'`


    ### 属性 Properties

    * `_microscope`：电镜对象
    * `_matter`：目标样品对象
    * `_center_strategy='xcorr2'`：归中方法，默认为互相关函数，默认为 `'xcorr2'`，可选方法为 `'none'`
    * `_denoise_strategy='bm3d'`：去噪方法，默认为 `'bm3d'`，可选方法为 `'none'`，`'gauss'`
    * `_opt_strategy='gd'`：最优化方法，默认为 `'gd'`
      * `_opt_strategy_kwargs={'Iteration':10, 'Alpha':1}`：最优化方法的输入参数
    * `_definition_evaluation_strategy='VGR'`：图像清晰度评价方法，默认为 `'VGR'`，可选方法为 'Variance', 'Laplacian', 'VGR', 'TGR', 'GDR'
    * `auto_focus_results`：输出结果，`0` 代表正常结束，当前状态即为自动聚焦的结果；`1` 代表发生 Runtime 错误

    ### 方法 Methods

    * `__init__(self, ztMicroscope, ztObject, **kwargs)`：Constructor
    * `run_auto_focus(self)`：开始自动聚焦（运行最优化进程）
    * `_check_properties`：检查输入
    * `_center_matter(self)`：将样品归中
    * `_denoise_image(self)`：将图像去噪
    * `_evaluate_definition(self)`：评价图片清晰度
    * `_opt_process(self)`：最优化进程
    """

    VALID_CENTER_STRATEGY = {'xcorr2'}

    def __init__(self, parent, microscope: ZtBaseMicroscope, obj: Optional[ZtObject],
                 center_strategy: str = 'xcorr2',
                 denoise_strategy: str = 'bm3d',
                 denoise_strategy_kwargs: dict = None,
                 opt_strategy: str = 'gd',
                 opt_strategy_kwargs: dict = None,
                 definition_evaluation_strategy: str = 'VGR',
                 ):
        # if opt_strategy_kwargs is None:
        #     opt_strategy_kwargs = {
        #         'OptMethod': 'dichotomy-GD',  # 优化方法
        #         'MaxIteration': 10,  # 最大迭代次数
        #         'OFRSStepSize': 20,  # OFRS 步骤的步长, nm
        #         'FRSStepSize': 20,  # FRS 步骤的步长, nm
        #     }
        # if denoise_strategy_kwargs is None:
        #     pass

        super().__init__()
        self.parent = parent
        self._microscope: ZtBaseMicroscope = microscope
        self._object: ZtObject = obj
        self._center_strategy: str = center_strategy
        self._denoise_strategy: str = denoise_strategy
        self._denoise_strategy_kwargs: dict = denoise_strategy_kwargs
        self._opt_strategy: str = opt_strategy
        self._opt_strategy_kwargs: dict = opt_strategy_kwargs
        self._definition_evaluation_strategy: str = definition_evaluation_strategy

        self._temp_image: ZtImage = ZtImage(None)
        self._curr_reference_image: np.ndarray = None
        self._denoiser: ZtDenoiser = ZtDenoiser()
        self._definition_evaluator: ZtDefinitionEvaluator = ZtDefinitionEvaluator()

        self.definition_list: list = []
        self.defocus_list: list = []
        self.auto_focus_results: int = 1

    def run(self):
        # try:
        # 先检查输入
        self._check_properties()
        # 再进行焦距优化
        self._opt_process()
        # 输出聚焦结果
        self.auto_focus_results = 1
        # except Exception as e:
        #     # 发生错误，记录错误结果
        #     print(e)
        #     self.auto_focus_results = 0
        return self.auto_focus_results

    def _check_properties(self):
        pass

    def _center_matter(self):
        # 将样品根据其参考图像进行归中
        # TODO: 判断异常漂移情况
        if self._center_strategy == 'xcorr2':
            # 获得当前样品的新参考图像与需要平移的像素量
            reference_image_data, _, _matter_d_position_pixel = extract_pattern(self._object.reference_image,
                                                                                self._temp_image._img)

            self._curr_reference_image = reference_image_data
            # 计算需要平移的量
            # TODO: 检查 ZtImage 对象的 metadata 属性
            pixel_size = [self._temp_image.metadata['PixelSize']['width'],
                          self._temp_image.metadata['PixelSize']['height']]
            _matter_d_position_real = np.array(_matter_d_position_pixel) * np.array(pixel_size) * 1E-4

            # 控制 Stage 进行平移
            _stage_position = self.microscope.get_stage()  # ! 可能调用 getter

            self.microscope.set_stage(x=_stage_position['x'] + _matter_d_position_real[1],
                                           y=_stage_position['y'] - _matter_d_position_real[0],
                                           z=None, a=None, b=None)

        elif self._center_strategy == 'none':
            pass
        else:
            raise ValueError(f'{self._center_strategy} is not a valid center strategy name.')

    def _capture_image(self):
        # 采集一张图片，得到 ZtImage 对象
        # TODO: 添加对图像异常（如 charging 情况）的判断
        acq_condition = self.parent._data_model.acq_condition
        self._temp_image = self.microscope.Acquisition.acquire_stem_image(**acq_condition)
        self.parent.update_main_figure(self._temp_image._img)

    def _export_progress(self, optimizer, denoised_image):
        self.parent.update_autofocus_info(self.defocus_list, self.definition_list,
                                          optimizer.defocus_list_smooth, optimizer.definition_list_smooth)
        self.parent.update_sample_figure(denoised_image)

    def _denoise_image(self, image_input: np.ndarray):
        self._denoiser._image_input = image_input
        self._denoiser._denoise_strategy = self._denoise_strategy
        self._denoiser._denoise_strategy_kwargs = self._denoise_strategy_kwargs
        denoised_image = self._denoiser.denoise()
        return denoised_image

    def _evaluate_definition(self, image_input: np.ndarray):
        self._definition_evaluator._image_input = image_input
        self._definition_evaluator._definition_evaluation_strategy = self._definition_evaluation_strategy
        image_definition = self._definition_evaluator.evaluate()
        return image_definition

    def _opt_process(self):
        # 最优化进程，为该 Strategy 的主程序，输入电镜和样品对象，输出需要的聚焦参数
        # 进程过程中的清晰度列表
        self.definition_list = []
        self.defocus_list = []

        self._opt_process_ofrs()
        self._opt_process_frs()

    def _opt_process_ofrs(self):
        # 离焦量较大时的聚焦方法
        _max_iteration = self._opt_strategy_kwargs['MaxIteration']
        print('\t[ztStemStrategy - ZtStemAutoFocus] Optimization process (OFRS) starts!')

        while True:
            # 首先采集一张图片，用于后面的所有流程
            print('Capture image...')
            self._capture_image()
            print('Capture finished')
            # 然后归中样品，并得到当前样品的图片 self._curr_reference_image
            self._center_matter()
            # 将获得的图像进行去噪
            denoised_image = self._denoise_image(self._curr_reference_image)
            # 对中间的特征图像去噪并评价清晰度
            image_definition = self._evaluate_definition(denoised_image)
            # 记录当前的清晰度和离焦量
            # TODO: ZtMicroscope 类中添加 Projection 属性
            self.definition_list.append(image_definition)
            self.defocus_list.append(self.microscope.Projection.defocus*1e3)
            print(self.defocus_list)
            # 实例化优化器对电镜参数进行优化
            optimizer = AutoFocusOptimizer(self, optimize_stage='OFRS')
            suggest_result = optimizer.get_opt_proposal()
            # 报告进度
            self._export_progress(optimizer, denoised_image)

            self.microscope.set_defocus(suggest_result['defocus']*1e-3)
            # self.microscope.set_stage(z=suggest_result['z'])

            # # update additional figure
            # self.root.event_generate("<<AutoFocusLoopUpdated>>")

            ind = np.argsort(self.defocus_list)
            # 按照 defocus 值排序的清晰度列表
            sdl = np.array(self.definition_list)[ind]
            # 如果不是单调，停止 OFRS 搜索
            if not is_monotonic(sdl):
                break

    def _opt_process_frs(self):
        print('\t[ztStemStrategy - ZtStemAutoFocus] Optimization process (FRS) starts!')
        # 离焦量较小时的聚焦方法
        loop_left = self._opt_strategy_kwargs['MaxIteration']

        while True:
            # 首先采集一张图片，用于后面的所有流程
            self._capture_image()
            # 然后归中样品，并得到当前样品的图片 self._curr_reference_image
            self._center_matter()
            # 将获得的图像进行去噪
            denoised_image = self._denoise_image(self._curr_reference_image)
            # 对中间的特征图像去噪并评价清晰度
            image_definition = self._evaluate_definition(denoised_image)
            # 记录当前的清晰度和离焦量
            # TODO: ZtMicroscope 类中添加 Projection 属性
            self.definition_list.append(image_definition)
            self.defocus_list.append(self.microscope.Projection.defocus*1e3)
            optimizer = AutoFocusOptimizer(self, optimize_stage='FRS')
            suggest_result = optimizer.get_opt_proposal()
            # 报告进度
            self._export_progress(optimizer, denoised_image)

            self.microscope.set_defocus(suggest_result['defocus']*1e-3)
            # self.microscope.set_stage(z=suggest_result['z'])

            # # update additional figure
            # self.contextModelObj.root.event_generate("<<AutoFocusLoopUpdated>>")

            # count
            loop_left -= 1
            if loop_left == 0:
                break

    @property
    def opt_strategy_kwargs(self):
        return self._opt_strategy_kwargs

    @property
    def microscope(self):
        return self.parent._control_thread.microscope


class AutoFocusOptimizer:
    def __init__(self, ztStemAutoFocus: ZtStemAutoFocus, optimize_stage):
        self.ztStemAutoFocus = ztStemAutoFocus
        self.optimize_stage = optimize_stage
        self.defocus_list = self.ztStemAutoFocus.defocus_list
        self.defocus_list_smooth = []
        self.definition_list = imrescale(self.ztStemAutoFocus.definition_list)
        self.definition_list_smooth = []
        self._opt_strategy_kwargs = self.ztStemAutoFocus.opt_strategy_kwargs

        self._microscope = self.ztStemAutoFocus.microscope
        self._switch_optimizer()

    def _switch_optimizer(self):
        if self._opt_strategy_kwargs['OptMethod'] == 'dichotomy-GD':
            pass
        else:
            raise ValueError("Unrecognized optimizer_method")

    def get_opt_proposal(self):
        if self.optimize_stage == 'OFRS':
            # 边界条件
            # 未进行优化
            if len(self.definition_list) <= 1:
                direction = -1 if self.defocus_list[-1] >= 0 else 1
                suggest_defocus = self.defocus_list[-1] + \
                                  self._opt_strategy_kwargs['OfrsStepSize'] * direction
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)
            # 进行了一步优化
            elif len(self.definition_list) == 2:
                gradient = (self.definition_list[1] - self.definition_list[0]) / \
                           (self.defocus_list[1] - self.defocus_list[0])
                direction = 1 if gradient >= 0 else -1
                start_point = self.defocus_list[1] if \
                    self.definition_list[1] >= self.definition_list[0] else self.defocus_list[0]
                suggest_defocus = start_point + direction * self._opt_strategy_kwargs['OfrsStepSize']
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)

            else:
                x_eps = 1
                self.defocus_list_smooth = np.arange(
                    np.ceil(np.min(self.defocus_list) * 10) / 10,
                    np.floor(np.max(self.defocus_list) * 10) / 10, x_eps)

                defocus_def_pair_func = interp1d(self.defocus_list, self.definition_list, kind='linear')

                curr_defocus = self.defocus_list[-1]
                ydata_def = defocus_def_pair_func(self.defocus_list_smooth)
                self.definition_list_smooth = gaussian_filter1d(ydata_def, sigma=3, mode='nearest')
                gradient_def = (self.definition_list_smooth[2:] - self.definition_list_smooth[:-2]) / x_eps
                defocus_ind = np.argmin(np.abs(self.defocus_list_smooth[:-2] - curr_defocus))
                gradient = gradient_def[defocus_ind]
                direction = 1 if gradient >= 0 else -1
                start_point = self.defocus_list[-1]
                suggest_defocus = start_point + direction * self._opt_strategy_kwargs['OfrsStepSize']
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)

        elif self.optimize_stage == 'FRS':
            x_eps = 1
            self.defocus_list_smooth = np.arange(
                np.ceil(np.min(self.defocus_list) * 10) / 10,
                np.floor(np.max(self.defocus_list) * 10) / 10, x_eps)

            defocus_def_pair_func = interp1d(self.defocus_list, self.definition_list, kind='linear')

            curr_defocus = self.defocus_list[-1]
            ydata_def = defocus_def_pair_func(self.defocus_list_smooth)
            self.definition_list_smooth = gaussian_filter1d(ydata_def, sigma=3, mode='nearest')
            gradient_def = (self.definition_list_smooth[2:] - self.definition_list_smooth[:-2]) / x_eps
            defocus_ind = np.argmin(np.abs(self.defocus_list_smooth[:-2] - curr_defocus))
            gradient = gradient_def[defocus_ind]

            suggest_defocus = self.defocus_list[-1] + gradient * self._opt_strategy_kwargs['FrsStepSize'] * 5
            suggest_z = None
            return dict(defocus=suggest_defocus, z=suggest_z)
