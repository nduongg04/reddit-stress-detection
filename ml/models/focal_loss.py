"""
Focal Loss implementation for handling class imbalance
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Focal Loss for addressing class imbalance

    FL(p_t) = -α_t * (1 - p_t)^γ * log(p_t)

    where:
    - p_t is the model's estimated probability for the true class
    - α_t is a weighting factor for class t
    - γ (gamma) is the focusing parameter (γ ≥ 0)

    When γ = 0, focal loss is equivalent to cross entropy loss.
    As γ increases, the loss focuses more on hard, misclassified examples.
    """

    def __init__(self, alpha=None, gamma=2.0, reduction='mean'):
        """
        Args:
            alpha: Weighting factor in [0, 1] to balance positive/negative examples
                   or a list of weights for each class
            gamma: Exponent of the modulating factor (1 - p_t)^gamma (default: 2.0)
            reduction: 'none' | 'mean' | 'sum'
        """
        super(FocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs, targets):
        """
        Args:
            inputs: (N, C) where C = number of classes (logits, not probabilities)
            targets: (N,) where each value is 0 ≤ targets[i] ≤ C-1

        Returns:
            Loss value
        """
        # Get probabilities
        p = F.softmax(inputs, dim=1)

        # Get class probabilities
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')
        p_t = p.gather(1, targets.view(-1, 1)).squeeze(1)

        # Calculate focal loss
        focal_weight = (1 - p_t) ** self.gamma
        focal_loss = focal_weight * ce_loss

        # Apply alpha weighting
        if self.alpha is not None:
            if isinstance(self.alpha, (float, int)):
                alpha_t = self.alpha
            else:
                # alpha is a tensor of class weights
                alpha_t = self.alpha.gather(0, targets)
            focal_loss = alpha_t * focal_loss

        # Apply reduction
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss


class WeightedFocalLoss(nn.Module):
    """
    Combination of class weighting and focal loss
    """

    def __init__(self, class_weights=None, gamma=2.0, reduction='mean'):
        super(WeightedFocalLoss, self).__init__()
        self.gamma = gamma
        self.class_weights = class_weights
        self.reduction = reduction

    def forward(self, inputs, targets):
        """
        Args:
            inputs: (N, C) logits
            targets: (N,) class labels
        """
        # Compute softmax probabilities
        p = F.softmax(inputs, dim=1)

        # Get the probability of the true class
        ce_loss = F.cross_entropy(inputs, targets, reduction='none')
        p_t = p.gather(1, targets.view(-1, 1)).squeeze(1)

        # Focal term: (1 - p_t)^gamma
        focal_weight = (1 - p_t) ** self.gamma

        # Weighted focal loss
        focal_loss = focal_weight * ce_loss

        # Apply class weights
        if self.class_weights is not None:
            if isinstance(self.class_weights, torch.Tensor):
                weight_t = self.class_weights.gather(0, targets)
                focal_loss = weight_t * focal_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss
