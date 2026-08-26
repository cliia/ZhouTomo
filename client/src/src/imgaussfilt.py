import cv2


def imgaussfilt(i_raw, **kwargs):
    if 'Kernel' in kwargs:
        k = kwargs['Kernel']
    else:
        k = (5, 5)

    i_blurred = cv2.GaussianBlur(i_raw, k, 0)
    return i_blurred
