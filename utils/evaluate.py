''' various functions for computing image quality metrics '''
import argparse
import pathlib
from argparse import ArgumentParser

import h5py
import scipy
import numpy as np
import torch
from runstats import Statistics
from skimage.metrics import peak_signal_noise_ratio as compare_psnr, \
                            structural_similarity as compare_ssim
from pytorch_msssim import ms_ssim


def normalize_img(img_out, img_gt):
    ''' normalize the pixel values in im_gt according to (mean, std) of im_out
        verified: step is necessary '''
    
    if img_out.mean() < img_gt.mean():
        raise NotImplementedError('assumes img_gt has smaller pixel vals')

    img_gt = (img_gt - img_gt.mean()) / img_gt.std()
    img_gt *= img_out.std()
    img_gt += img_out.mean()
    
    return img_gt

def calc_metrics(img_out, img_gt):
    ''' compute vif, ssim, and psnr of img_out using im_gt as ground-truth reference '''
   
    img_gt = normalize_img(img_out, img_gt)

    vif_ = vifp_mscale(img_out, img_gt, sigma_nsq=img_out.mean())
    ssim_ = ssim(np.array([img_out]), np.array([img_gt]))
    psnr_ = psnr(np.array([img_out]), np.array([img_gt]))
    
    dt = torch.FloatTensor
    img_out_t = torch.from_numpy(np.array([[img_out]])).type(dt)
    img_gt_t = torch.from_numpy(np.array([[img_gt]])).type(dt)
    msssim_ = ms_ssim(img_out_t, img_gt_t, data_range=img_gt_t.max())
    msssim_ = msssim_.data.cpu().numpy()[np.newaxis][0]
    
    return vif_, msssim_, ssim_, psnr_ 

def mse(gt, pred):
    """ Compute Mean Squared Error (MSE) """
    return np.mean((gt - pred) ** 2)


def nmse(gt, pred):
    """ Compute Normalized Mean Squared Error (NMSE) """
    return np.linalg.norm(gt - pred) ** 2 / np.linalg.norm(gt) ** 2


def psnr(gt, pred):
    """ Compute Peak Signal to Noise Ratio metric (PSNR) """
    return compare_psnr(gt, pred, data_range=gt.max())


def ssim(gt, pred):
    """ Compute Structural Similarity Index Metric (SSIM). """
    return compare_ssim(
        gt.transpose(1, 2, 0), pred.transpose(1, 2, 0), multichannel=True, data_range=gt.max()
    )

def vifp_mscale(ref, dist,sigma_nsq=1,eps=1e-10):
    ### from https://github.com/aizvorski/video-quality/blob/master/vifp.py
    sigma_nsq = sigma_nsq  ### tune this for your dataset to get reasonable numbers
    eps = eps

    num = 0.0
    den = 0.0
    for scale in range(1, 5):
       
        N = 2**(4-scale+1) + 1
        sd = N/5.0

        if (scale > 1):
            ref = scipy.ndimage.gaussian_filter(ref, sd)
            dist = scipy.ndimage.gaussian_filter(dist, sd)
            ref = ref[::2, ::2]
            dist = dist[::2, ::2]
                
        mu1 = scipy.ndimage.gaussian_filter(ref, sd)
        mu2 = scipy.ndimage.gaussian_filter(dist, sd)
        mu1_sq = mu1 * mu1
        mu2_sq = mu2 * mu2
        mu1_mu2 = mu1 * mu2
        sigma1_sq = scipy.ndimage.gaussian_filter(ref * ref, sd) - mu1_sq
        sigma2_sq = scipy.ndimage.gaussian_filter(dist * dist, sd) - mu2_sq
        sigma12 = scipy.ndimage.gaussian_filter(ref * dist, sd) - mu1_mu2
        
        sigma1_sq[sigma1_sq<0] = 0
        sigma2_sq[sigma2_sq<0] = 0
        
        g = sigma12 / (sigma1_sq + eps)
        sv_sq = sigma2_sq - g * sigma12
        
        g[sigma1_sq<eps] = 0
        sv_sq[sigma1_sq<eps] = sigma2_sq[sigma1_sq<eps]
        sigma1_sq[sigma1_sq<eps] = 0
        
        g[sigma2_sq<eps] = 0
        sv_sq[sigma2_sq<eps] = 0
        
        sv_sq[g<0] = sigma2_sq[g<0]
        g[g<0] = 0
        sv_sq[sv_sq<=eps] = eps
        
        num += np.sum(np.log10(1 + g * g * sigma1_sq / (sv_sq + sigma_nsq)))
        den += np.sum(np.log10(1 + sigma1_sq / sigma_nsq))
        
    vifp = num/den

    return vifp

METRIC_FUNCS = dict(
    MSE=mse,
    NMSE=nmse,
    PSNR=psnr,
    SSIM=ssim,
    VIF=vifp_mscale,
)


class Metrics:
    """
    Maintains running statistics for a given collection of metrics.
    """

    def __init__(self, metric_funcs):
        self.metrics = {
            metric: Statistics() for metric in metric_funcs
        }

    def push(self, target, recons):
        for metric, func in METRIC_FUNCS.items():
            self.metrics[metric].push(func(target, recons))

    def means(self):
        return {
            metric: stat.mean() for metric, stat in self.metrics.items()
        }

    def stddevs(self):
        return {
            metric: stat.stddev() for metric, stat in self.metrics.items()
        }

    def __repr__(self):
        means = self.means()
        stddevs = self.stddevs()
        metric_names = sorted(list(means))
        return ' '.join(
            f'{name} = {means[name]:.4g} +/- {2 * stddevs[name]:.4g}' for name in metric_names
        )


def evaluate(args, recons_key):
    metrics = Metrics(METRIC_FUNCS)

    for tgt_file in args.target_path.iterdir():
        with h5py.File(tgt_file) as target, h5py.File(
          args.predictions_path / tgt_file.name) as recons:
            if args.acquisition and args.acquisition != target.attrs['acquisition']:
                continue
            target = target[recons_key].value
            recons = recons['reconstruction'].value
            metrics.push(target, recons)
    return metrics


if __name__ == '__main__':
    parser = ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--target-path', type=pathlib.Path, required=True,
                        help='Path to the ground truth data')
    parser.add_argument('--predictions-path', type=pathlib.Path, required=True,
                        help='Path to reconstructions')
    parser.add_argument('--challenge', choices=['singlecoil', 'multicoil'], required=True,
                        help='Which challenge')
    parser.add_argument('--acquisition', choices=['CORPD_FBK', 'CORPDFS_FBK'], default=None,
                        help='If set, only volumes of the specified acquisition type are used '
                             'for evaluation. By default, all volumes are included.')
    args = parser.parse_args()

    recons_key = 'reconstruction_rss' if args.challenge == 'multicoil' else 'reconstruction_esc'
    metrics = evaluate(args, recons_key)
    print(metrics)
