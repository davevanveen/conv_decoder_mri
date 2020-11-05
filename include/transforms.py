"""
Copyright (c) Facebook, Inc. and its affiliates.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import numpy as np
import torch


#def to_tensor(data):
#    """
#    Convert numpy array to PyTorch tensor. For complex arrays, the real and imaginary parts
#    are stacked along the last dimension.
#
#    Args:
#        data (np.array): Input numpy array
#
#    Returns:
#        torch.Tensor: PyTorch version of data
#    """
#    if np.iscomplexobj(data):
#        data = np.stack((data.real, data.imag), axis=-1)
#    return torch.from_numpy(data)


def apply_mask(data, mask_func = None, mask = None, seed=None):
    """
    Subsample given k-space by multiplying with a mask.

    Args:
        data (torch.Tensor): The input k-space data. This should have at least 3 dimensions, where
            dimensions -3 and -2 are the spatial dimensions, and the final dimension has size
            2 (for complex values).
        mask_func (callable): A function that takes a shape (tuple of ints) and a random
            number seed and returns a mask.
        seed (int or 1-d array_like, optional): Seed for the random number generator.

    Returns:
        (tuple): tuple containing:
            masked data (torch.Tensor): Subsampled k-space data
            mask (torch.Tensor): The generated mask
    """
    shape = np.array(data.shape)
    shape[:-3] = 1
    if mask is None:
        mask = mask_func(shape, seed)
    return data * mask, mask


def fft2(arr):
    raise ImportError('fft2() deprecated. see utils.transform.py for fft_2d()')

def ifft2(data):
    raise ImportError('ifft2() deprecated. see utils.transform.py for ifft_2d()')

# TODO: delete. data should never be in this format
#def complex_abs(data):
#    """
#    Compute the absolute value of a complex valued input tensor.
#
#    Args:
#        data (torch.Tensor): A complex valued tensor, where the size of the final dimension
#            should be 2.
#
#    Returns:
#        torch.Tensor: Absolute value of data
#    """
#    assert data.size(-1) == 2
#    return (data ** 2).sum(dim=-1).sqrt()


# TODO: replace w updated function
#def root_sum_of_squares(data, dim=0):
#    """
#    Compute the Root Sum of Squares (RSS) transform along a given dimension of a tensor.
#
#    Args:
#        data (torch.Tensor): The input tensor
#        dim (int): The dimensions along which to apply the RSS transform
#
#    Returns:
#        torch.Tensor: The RSS value
#    """
#    return torch.sqrt((data ** 2).sum(dim))


def center_crop(data, shape):
    """
    Apply a center crop to the input real image or batch of real images.

    Args:
        data (torch.Tensor): The input tensor to be center cropped. It should have at
            least 2 dimensions and the cropping is applied along the last two dimensions.
        shape (int, int): The output shape. The shape should be smaller than the
            corresponding dimensions of data.

    Returns:
        torch.Tensor: The center cropped image
    """
    assert 0 < shape[0] <= data.shape[-2]
    assert 0 < shape[1] <= data.shape[-1]
    w_from = (data.shape[-2] - shape[0]) // 2
    h_from = (data.shape[-1] - shape[1]) // 2
    w_to = w_from + shape[0]
    h_to = h_from + shape[1]
    return data[..., w_from:w_to, h_from:h_to]


def complex_center_crop(data, shape):
    """
    Apply a center crop to the input image or batch of complex images.

    Args:
        data (torch.Tensor): The complex input tensor to be center cropped. It should
            have at least 3 dimensions and the cropping is applied along dimensions
            -3 and -2 and the last dimensions should have a size of 2.
        shape (int, int): The output shape. The shape should be smaller than the
            corresponding dimensions of data.

    Returns:
        torch.Tensor: The center cropped image
    """
    assert 0 < shape[0] <= data.shape[-3]
    assert 0 < shape[1] <= data.shape[-2]
    w_from = (data.shape[-3] - shape[0]) // 2
    h_from = (data.shape[-2] - shape[1]) // 2
    w_to = w_from + shape[0]
    h_to = h_from + shape[1]
    return data[..., w_from:w_to, h_from:h_to, :]


def normalize(data, mean, stddev, eps=0.):
    """
    Normalize the given tensor using:
        (data - mean) / (stddev + eps)

    Args:
        data (torch.Tensor): Input data to be normalized
        mean (float): Mean value
        stddev (float): Standard deviation
        eps (float): Added to stddev to prevent dividing by zero

    Returns:
        torch.Tensor: Normalized tensor
    """
    return (data - mean) / (stddev + eps)


def normalize_instance(data, eps=0.):
    """
        Normalize the given tensor using:
            (data - mean) / (stddev + eps)
        where mean and stddev are computed from the data itself.

        Args:
            data (torch.Tensor): Input data to be normalized
            eps (float): Added to stddev to prevent dividing by zero

        Returns:
            torch.Tensor: Normalized tensor
        """
    mean = data.mean()
    std = data.std()
    return normalize(data, mean, std, eps), mean, std
