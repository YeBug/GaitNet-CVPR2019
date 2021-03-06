import time

import torchvision
import torch
import torch.backends.cudnn as cudnn
cudnn.deterministic = True
cudnn.benchmark = False


class MRCNN():
    def __init__(self, is_gpu):
        self.model = torchvision.models.detection.maskrcnn_resnet50_fpn(pretrained=True)
        # pretrained (bool) – If True, returns a model pre-trained on COCO train2017

        self.model.eval()
        # set it to evaluation mode, as the model behaves differently
        if is_gpu:
            self.model.cuda()

        self.cont = True

    def reset(self):
        self.cont = True

    def __apply_mask(self,image, mask):
        """Apply the given mask to the image.
        """
        masked_image = torch.zeros(image.shape, dtype=image.dtype).cuda()
        for c in range(3):
            masked_image[c] = image[c]*mask[0]
        return masked_image

    def __filter_person_and_select_top(self,mrcnn_output, threshold, top):
        """
        filter out person(id:1) instance only

        It seeeeeeeeeems that torchvision give us the order already sorted by score!
        EVIDENCE:
        haha  = mrcnn_output['scores'].tolist()
        print(np.argsort(haha))


        return NONE if no requirement meet
        """
        mrcnn_output_filtered = {
            'boxes':[],
            # 'labels': [],
            'scores': [],
            'masks': [],

        }
        for bbox,label,score,mask in zip(mrcnn_output['boxes'],
                        mrcnn_output['labels'],
                        mrcnn_output['scores'],
                        mrcnn_output['masks']):
            if label.item() == 1 and score.item() > threshold:
                mrcnn_output_filtered['boxes'].append(bbox)
                # mrcnn_output_filtered['labels'].append(label)
                mrcnn_output_filtered['scores'].append(score)
                mrcnn_output_filtered['masks'].append(mask)
        if len(mrcnn_output_filtered['boxes']) != 0:
            mrcnn_output_filtered['boxes'] = torch.stack(mrcnn_output_filtered['boxes'])[:top]
            mrcnn_output_filtered['scores'] = torch.stack(mrcnn_output_filtered['scores'])[:top]
            mrcnn_output_filtered['masks'] = torch.stack(mrcnn_output_filtered['masks'])[:top]
            return mrcnn_output_filtered
        return None

    def __out_of_frame(self,silhouette_full,space):
        top = silhouette_full[:,0:space,:]
        bottom = silhouette_full[:,silhouette_full.shape[1]-space:silhouette_full.shape[1],:]
        left = silhouette_full[:,:,:space]
        right = silhouette_full[:,:,silhouette_full.shape[2]-space:silhouette_full.shape[2]]
        return torch.sum(bottom).item() != 0 \
               or torch.sum(top).item() != 0 \
               or torch.sum(left).item() != 0 \
               or torch.sum(right).item() != 0

    def __bbox_crop(self,frame,box):
        box = [int(e) for e in box]
        x0, y0, x1, y1 = box
        x_c = (x0 + x1) // 2
        y_c = (y0 + y1) // 2

        height = int((y1 - y0)*1.5)

        if height % 2 != 0:
            height += 1
        width = height // 2
        return frame[:,
               y_c - height // 2:y_c - height // 2 + height,
               x_c - width // 2:x_c - width // 2 + width] # maybe empty if subject too close to boundry

    def process_batch(self,batch,threshold,top_num,out_of_frame_space, dataset):
        result_filtered = []
        segmentations_full = []
        silhouettes_full = []

        segmentations_part = []
        silhouettes_part = []
        crops_part = []

        result = self.model(batch[:]) # seems the batch is mutable here

        for img, one in zip(batch, result):

            output_person = self.__filter_person_and_select_top(one, threshold, top_num)
            # result_filtered.append(output_person)
            if output_person is None:
                continue

            silhouette = output_person['masks'][0]
            segmentation = self.__apply_mask(img, silhouette)
            box = output_person['boxes'][0].tolist()

            segmentation_ = self.__bbox_crop(segmentation, box)
            silhouette_ = self.__bbox_crop(silhouette,box)
            crop = self.__bbox_crop(img,box)


            if dataset == 'FVG':
                if self.cont:
                    if not self.__out_of_frame(silhouette,out_of_frame_space):
                            segmentations_part.append(segmentation_)
                            silhouettes_part.append(silhouette_)
                            crops_part.append(crop)
                    else:
                        self.cont = False
            elif dataset in ['CB', 'USF']:
                # if self.cont:
                if not self.__out_of_frame(silhouette,out_of_frame_space):
                        segmentations_part.append(segmentation_)
                        silhouettes_part.append(silhouette_)
                        crops_part.append(crop)
                    # else:
                    #     self.cont = False

        return segmentations_part, silhouettes_part, crops_part





