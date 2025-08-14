from model.ztImage import ZtImage
from src.BM3D_Main import bm3d_main
from src.imgaussfilt import imgaussfilt
from src.utils import imnorm, imrescale


class ZtDenoiser:
    def __init__(self, image_input: ZtImage = None, denoise_strategy: str = 'bm3d', denoise_strategy_kwargs: dict = None):
        self._image_input = image_input
        self._denoise_strategy = denoise_strategy
        self._denoise_strategy_kwargs = denoise_strategy_kwargs

    def denoise(self):
        i_raw = self._image_input.data
        if self._denoise_strategy == 'bm3d':
            if self._denoise_strategy_kwargs is not None:
                i_denoised = bm3d_main(i_raw, **self._denoise_strategy_kwargs)
            else:
                i_denoised = bm3d_main(i_raw)
        elif self._denoise_strategy == 'gauss':
            if self._denoise_strategy_kwargs is not None:
                i_denoised = imgaussfilt(i_raw, **self._denoise_strategy_kwargs)
            else:
                i_denoised = imgaussfilt(i_raw)
        elif self._denoise_strategy == 'none':
            i_denoised = i_raw
        else:
            raise ValueError(f'{self._denoise_strategy} is not a valid denoise strategy name.')

        _denoised_image = imnorm(imrescale(i_denoised, (0, 255)),
                                 50 * i_denoised.shape[0] * i_denoised.shape[1])
        return _denoised_image
