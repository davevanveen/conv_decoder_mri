import os, sys
import numpy as np
from os import listdir
from os.path import isfile, join
import matplotlib.pyplot as plt
import h5py
import sigpy
from sigpy.mri.samp import poisson
import torch

sys.path.append('/home/vanveen/ConvDecoder/')
from utils.helpers import num_params#, get_masks
from include.decoder_conv import init_convdecoder
from include.fit import fit
from utils.evaluate import calc_metrics
from utils.transform import fft_2d, ifft_2d, root_sum_squares, \
                            reshape_complex_vals_to_adj_channels, \
                            reshape_adj_channels_to_complex_vals

if torch.cuda.is_available():
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True
    dtype = torch.cuda.FloatTensor
    torch.cuda.set_device(1)


def run_expmt():

    path_in = '/bmrNAS/people/arjun/data/qdess_knee_2020/files_recon_calib-16/'
    #path_in = '/bmrNAS/people/dvv/in_qdess/'
    files = [f for f in listdir(path_in) if isfile(join(path_in, f))]
    files.sort()
    NUM_SAMPS = 25 # number of samples to recon
       
    NUM_ITER = 10000
    path_out = '/bmrNAS/people/dvv/out_qdess/'

    # load mask, force central CxC pixels in mask to be 1
    mask = torch.from_numpy(np.load('ipynb/mask_3d.npy'))
    mask = abs(mask).type(torch.uint8)
    idx_y, idx_z = mask.shape[0] // 2, mask.shape[1] // 2
    C = 32
    mask[idx_y-C:idx_y+C, idx_z-C:idx_z+C] = 1

    for fn in files[:NUM_SAMPS]:

        # load data
        f = h5py.File(path_in + fn, 'r')
        try:
            ksp = torch.from_numpy(f['kspace'][()])
        except KeyError:
            print('No kspace in file {} w keys {}'.format(fn, f.keys()))
            f.close()
            continue
        f.close()
        #fn_npy_in = '/bmrNAS/people/dvv/in_qdess/{}_kspace.npy'.format(fn.split('.h5')[0])
        #ksp = torch.from_numpy(np.load(fn_npy_in))
        ksp_vol = ksp[:,:,:,0,:].permute(3,0,1,2) # get echo1, reshape to be (nc, kx, ky, kz)

        # get central slice in kx, i.e. axial plane b/c we undersample in (ky, kz)
        idx_kx = ksp_vol.shape[1] // 2
        ksp_orig = ksp_vol[:, idx_kx, :, :]

        # initialize network
        net, net_input, ksp_orig_ = init_convdecoder(ksp_orig, mask)

        # apply mask after rescaling k-space. want complex tensors dim (nc, ky, kz)
        ksp_masked = ksp_orig_ * mask
        img_masked = ifft_2d(ksp_masked)

        # fit network, get net output
        net, mse_wrt_ksp, mse_wrt_img = fit(
            ksp_masked=ksp_masked, img_masked=img_masked,
            net=net, net_input=net_input, mask2d=mask, num_iter=NUM_ITER)
        img_out = net(net_input.type(dtype))[0] # real tensor dim (2*nc, kx, ky)
        img_out = reshape_adj_channels_to_complex_vals(img_out) # complex tensor dim (nc, kx, ky)
        
        # perform dc step
        ksp_est = fft_2d(img_out)
        ksp_dc = torch.where(mask, ksp_masked, ksp_est) # dc step

        # create data-consistent, ground-truth images from k-space
        img_dc = root_sum_squares(ifft_2d(ksp_dc)).detach()
        img_gt = root_sum_squares(ifft_2d(ksp_orig))

        # save results
        samp = fn.split('.h5')[0] 
        np.save('{}{}_dc.npy'.format(path_out, samp), img_dc)
        np.save('{}{}_gt.npy'.format(path_out, samp), img_gt)

        print('recon {} w shape {}'.format(samp, ksp_vol.shape)) 

    return


if __name__ == '__main__':
    run_expmt()
