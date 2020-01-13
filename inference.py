"""
Usage: python inference.py [model_path] [image_path] [out_path] [device]

Run inference of the cracknausnet model on one specified image
"""

import numpy as np
import argparse
import torch
import cv2
import torchvision.transforms as transforms
from torch.autograd import Variable
import torch.nn.functional as F
from TernausNet.unet_models import UNet16
from patcher import split_in_chunks, merge_from_chunks
from matplotlib import pyplot as plt

class CrackDetector():
  def __init__(self, model_path, device='cuda:0'):
    self.module_name = 'crack detector'
    self.device = torch.device(device)
    
    # load model
    self.model = UNet16(pretrained=True, num_classes=3, is_deconv=True)
    checkpoint = torch.load(model_path)
    self.model.load_state_dict(checkpoint['model'])

    # move to device (GPU) and set mode to evaluation
    self.model.to(self.device)
    self.model.eval()


  def run(self, image_path, out_path):
    # load image
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    h_orig, w_orig, _ = img.shape

    # make divisible by 32 to use fully convolutional property
#    h_tmp = 32*round(h_orig / 32)
#    w_tmp = 32*round(w_orig / 32)
#    img_tmp = cv2.resize(img, (w_tmp, h_tmp), cv2.INTER_AREA)
    img_tmp = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)

    # determine preprocessing transformations (values from ImageNet)
    channel_means = [0.485, 0.456, 0.406]
    channel_stds  = [0.229, 0.224, 0.225]
    tfms = transforms.Compose([
        transforms.ToTensor(), 
        transforms.Normalize(channel_means, channel_stds)
      ])

    # set used input size for fully-convolutional network
    # (depends on GPU memory, input size of net is 448x448)
    size=3*448
    padding=32

    # split image into patches
    patches = split_in_chunks(img_tmp, size=size, padding=padding)

    # container for predictions
    predicts = []

    # loop over all patches
    for patch in patches:
      # transform patch
      X = tfms(patch)

      # add batch dimension
      X = Variable(X.unsqueeze(0)).to(self.device)  # [N, C, H, W]

      # compute forward pass
      pred = self.model(X)
     
      # apply softmax on output
      pred = F.softmax(pred, dim=1).data.cpu().numpy()

      # select relevant class (pred[0,0,:,:] non-crack, pred[0,1,:,:] is planking pattern)
      pred = pred[0,args.category,:,:]

      # append to results
      predicts.append(pred)

    # re-merge the patches into one image
    img_res = merge_from_chunks(predicts, h_orig, w_orig, size=size, padding=padding)

    # shape back to original size
    img_res = cv2.resize(img_res, (w_orig, h_orig), cv2.INTER_AREA)

    # save heatmap
    cv2.imwrite(out_path, img_res*255)

    # save overlayed image (225/2 for nicer use of color map)
    img_res = np.uint8(cv2.cvtColor(img_res.astype('float32'), cv2.COLOR_GRAY2BGR) * 255/2)
    img_res = cv2.applyColorMap(img_res, cv2.COLORMAP_HOT)
    cv2.imwrite(out_path.replace('.jpg', '_overlay.jpg'), cv2.addWeighted(img, 0.9, img_res, 0.8, 0))
    


if __name__ == "__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument('--model_path', type=str, default='./models/model_weights_cracknausnet.pt', required=False, help='path to model weights')
  parser.add_argument('--image_path', type=str, default='./uav75/test_img/DSC00595.jpg', required=False, help='path to input image')
  parser.add_argument('--out_path', type=str, default='./results/DSC00595.jpg', required=False, help='path to which the prediction is saved')
  parser.add_argument('--device', type=str, default='cuda:0', required=False, help='device to used for inference')
  parser.add_argument('--category', type=int, default=2, required=False, help='selected category (1: planking pattern, 2: crack)')
  args = parser.parse_args()

  detector = CrackDetector(args.model_path, args.device)
  detector.run(args.image_path, args.out_path)

