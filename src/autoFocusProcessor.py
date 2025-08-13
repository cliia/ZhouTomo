import cv2
import numpy as np
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d

from .normxcorr2 import extract_pattern
from .BM3D_Main import bm3d_main
from src import utils


class AutoFocusProcessor:
    """
    Parameters
    ----------
        contextModelObj : model.context_data.ContextData class. Context model.
        optimize_stage : str. 'OFRS', 'FRS', 'both'. Specify the optimization stage.
        evaluate_method : str. Specify the method of focus value (FV) evaluation. Valid methods are 'Variance',
            'Laplacian', 'VGR', 'TGR', 'GDR'.
        optimizer : list or str. The optimizer for defocus optimization.
    """

    def __init__(self, contextModelObj, optimize_stage='both', evaluate_method='VGR', optimizer='dichotomy-GD'):
        self.contextModelObj = contextModelObj
        self.optimize_stage = optimize_stage
        self.evaluate_method = evaluate_method
        self.optimizer = optimizer

        # check preconditions
        self._check_preconditions()
        # preprocess properties
        self.denoise_func = 'BM3D'
        self.denoise_options = None
        self.curr_target = self.contextModelObj.microscopeData.target_image
        self.curr_pattern_denoised = None
        # autofocus properties
        self.num_iters_ofrs = -1  # -1 means auto-stopped
        self.step_size_ofrs = 30
        self.num_iters_frs = 5

        # FV - defocus paired value
        self.FV_list = []
        self.defocus_list = []

    def _check_preconditions(self):
        """Check if the preconditions satisfy optimization."""
        # if isexist(target)
        if self.contextModelObj.microscopeData.target_image is None:
            raise RuntimeError('Target not specified!')

    def _preprocess(self):
        """
        Preprocess the image for evaluating FV
        Workflow of preprocess for individual image is:
            extract target - denoise - (background subtraction) - (weight matrix)

        Properties related
        ------------------
            self.denoise_func : str. 'Gaussian', 'Median', or 'BM3D'
            self.denoise_options : dict.
            self.curr_target : np.ndarray. Target for recognition. Updating every iteration.

        Output
        ------
            curr_pattern_denoised : The pattern extracted from the STEM image acquired in this loop.
        """
        curr_image = self.contextModelObj.microscopeData.curr_stem_image
        template = self.contextModelObj.microscopeData.target_image

        # Extract patterns
        curr_pattern, pos = extract_pattern(template, curr_image)
        print(curr_image.shape, pos)
        self.center_target(curr_image.shape, pos)

        # Denoise
        self.curr_pattern_denoised = None
        if self.denoise_func == 'Gaussian':
            # options
            kernel_size = 5

            self.curr_pattern_denoised = utils.imnorm(
                utils.imrescale(cv2.GaussianBlur(curr_pattern, (kernel_size, kernel_size), 0), (0, 255)),
                50 * curr_pattern.shape[0] * curr_pattern.shape[1]).astype(np.uint8)
        elif self.denoise_func == 'Median':
            # options
            kernel_size = 5

            self.curr_pattern_denoised = utils.imnorm(
                utils.imrescale(cv2.medianBlur(curr_pattern, kernel_size, 0), (0, 255)),
                50 * curr_pattern.shape[0] * curr_pattern.shape[1]).astype(np.uint8)
        elif self.denoise_func == 'BM3D':
            # options
            min_size = 1000
            disk_size = 15

            self.curr_pattern_denoised = utils.imnorm(
                utils.imrescale(bm3d_main(curr_pattern, MinSize=min_size, DiskSize=disk_size), (0, 255)),
                50 * curr_pattern.shape[0] * curr_pattern.shape[1]).astype(np.uint8)
        else:
            raise ValueError

    def _get_FV(self, image):
        definition, _ = utils.get_definition(image, EvalMethod=self.evaluate_method)
        return definition

    def _OFRS_loop(self):
        loop_left = self.num_iters_ofrs

        while True:
            self.contextModelObj.microscopeData.acquire()
            self._preprocess()
            definition = self._get_FV(self.curr_pattern_denoised)

            # Record the FV - defocus pair data
            self.FV_list.append(definition)
            self.defocus_list.append(self.contextModelObj.microscopeData.microscope.defocus)

            optimizer = Optimizer(self, curr_optimize_stage='OFRS')
            suggest_result = optimizer.get_opt_suggest()

            self.contextModelObj.microscopeData.microscope.defocus = suggest_result['defocus']
            self.contextModelObj.microscopeData.microscope.z = suggest_result['z']

            # update additional figure
            self.contextModelObj.root.event_generate("<<AutoFocusLoopUpdated>>")

            # count
            loop_left = loop_left - 1
            if loop_left == 0:
                break

            ind = np.argsort(self.defocus_list)
            if not utils.is_monotonic(np.array(self.FV_list)[ind]):
                break

    def _FRS_loop(self):
        loop_left = self.num_iters_frs

        while True:
            self.contextModelObj.microscopeData.acquire()
            self._preprocess()
            definition = self._get_FV(self.curr_pattern_denoised)

            # Record the FV - defocus pair data
            self.FV_list.append(definition)
            self.defocus_list.append(self.contextModelObj.microscopeData.microscope.defocus)

            optimizer = Optimizer(self, curr_optimize_stage='FRS')
            suggest_result = optimizer.get_opt_suggest()

            self.contextModelObj.microscopeData.microscope.defocus = suggest_result['defocus']
            self.contextModelObj.microscopeData.microscope.z = suggest_result['z']

            # update additional figure
            self.contextModelObj.root.event_generate("<<AutoFocusLoopUpdated>>")

            # count
            loop_left = loop_left - 1
            if loop_left == 0:
                break

    def run_autofocus(self):
        """Return the best defocus value."""
        self.FV_list = []
        self.defocus_list = []

        if self.optimize_stage == 'OFRS':
            self._OFRS_loop()
        elif self.optimize_stage == 'FRS':
            self._FRS_loop()
        elif self.optimize_stage == 'both':
            self._OFRS_loop()
            self._FRS_loop()
        else:
            raise ValueError('Invalid evalution_method')

    def center_target(self, image_shape, pos):
        print(pos)
        print(((np.array(image_shape)+1)/2))
        dpos = pos - ((np.array(image_shape)+1)/2)
        res = self.contextModelObj.microscopeData.microscope.pixel_size
        self.contextModelObj.microscopeData.microscope.x += dpos[0] * res
        self.contextModelObj.microscopeData.microscope.y += dpos[1] * res


# Optimizer
class Optimizer:
    def __init__(self, autofocus_processor: AutoFocusProcessor, curr_optimize_stage):
        self.autofocus_processor = autofocus_processor
        self._switch_optimizer()
        self.curr_optimize_stage = curr_optimize_stage

        self.defocus_list = self.autofocus_processor.defocus_list
        self.FV_list = utils.imrescale(self.autofocus_processor.FV_list)

        self.microscope = self.autofocus_processor.contextModelObj.microscopeData.microscope

    def _switch_optimizer(self):
        if self.autofocus_processor.optimizer == 'dichotomy-GD':
            pass
        else:
            raise ValueError("Unrecognized optimizer_method")

    def get_opt_suggest(self):
        if self.curr_optimize_stage == 'OFRS':
            if len(self.FV_list) <= 1:
                direction = -1 if self.defocus_list[-1] >= 0 else 1
                suggest_defocus = self.defocus_list[-1] + self.autofocus_processor.step_size_ofrs * direction
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)

            elif len(self.FV_list) == 2:
                gradient = (self.FV_list[1] - self.FV_list[0]) / \
                           (self.defocus_list[1] - self.defocus_list[0])
                direction = 1 if gradient >= 0 else -1
                start_point = self.defocus_list[1] if self.FV_list[1] >= self.FV_list[0] else self.defocus_list[0]
                suggest_defocus = start_point + direction * self.autofocus_processor.step_size_ofrs
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)

            else:
                x_eps = 1
                xdata_defocus = np.arange(
                    np.ceil(np.min(self.defocus_list) * 10) / 10,
                    np.floor(np.max(self.defocus_list) * 10) / 10, x_eps)

                defocus_FV_pair_func = interp1d(self.defocus_list, self.FV_list, kind='linear')

                curr_defocus = self.defocus_list[-1]
                ydata_FV = defocus_FV_pair_func(xdata_defocus)
                ydata_FV_smoothed = gaussian_filter1d(ydata_FV, sigma=3, mode='nearest')
                gradient_FV = (ydata_FV_smoothed[2:] - ydata_FV_smoothed[:-2]) / x_eps
                defocus_ind = np.argmin(np.abs(xdata_defocus[:-2] - curr_defocus))
                gradient = gradient_FV[defocus_ind]
                direction = 1 if gradient >= 0 else -1
                start_point = self.defocus_list[-1]
                suggest_defocus = start_point + direction * self.autofocus_processor.step_size_ofrs
                suggest_z = None
                return dict(defocus=suggest_defocus, z=suggest_z)

        elif self.curr_optimize_stage == 'FRS':
            x_eps = 1
            xdata_defocus = np.arange(
                np.ceil(np.min(self.defocus_list)*10)/10,
                np.floor(np.max(self.defocus_list)*10)/10, x_eps)

            defocus_FV_pair_func = interp1d(self.defocus_list, self.FV_list, kind='linear')

            curr_defocus = self.defocus_list[-1]
            ydata_FV = defocus_FV_pair_func(xdata_defocus)
            ydata_FV_smoothed = gaussian_filter1d(ydata_FV, sigma=3, mode='nearest')
            gradient_FV = (ydata_FV_smoothed[2:] - ydata_FV_smoothed[:-2]) / x_eps
            defocus_ind = np.argmin(np.abs(xdata_defocus[:-2] - curr_defocus))
            gradient = gradient_FV[defocus_ind]

            suggest_defocus = self.defocus_list[-1] + gradient * self.autofocus_processor.step_size_ofrs * 5
            suggest_z = None
            return dict(defocus=suggest_defocus, z=suggest_z)
