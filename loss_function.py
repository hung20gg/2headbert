from typing import Union, Callable
import torch
from itertools import count
import torch.nn as nn
import torch.nn.functional as F

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

def kl_loss(input, target, reduction='batchmean'):
    return F.kl_div(
        F.log_softmax(input, dim=-1),
        F.softmax(target, dim=-1),
        reduction=reduction,
    )

def sym_kl_loss(input, target, reduction='sum', alpha=1.0):
    return alpha * F.kl_div(
        F.log_softmax(input, dim=-1),
        F.softmax(target.detach(), dim=-1),
        reduction=reduction,
    ) + F.kl_div(
        F.log_softmax(target, dim=-1),
        F.softmax(input.detach(), dim=-1),
        reduction=reduction,
    )

def exists(val):
    return val is not None

def default(val, d):
    if exists(val):
        return val
    return d

def inf_norm(x):
    return torch.norm(x, p=float('inf'), dim=-1, keepdim=True)
class SMARTLoss(nn.Module):
    
    def __init__(
        self,
        eval_fn: Callable,
        loss_fn: Callable,
        loss_last_fn: Callable = None, 
        norm_fn: Callable = inf_norm, 
        num_steps: int = 1,
        step_size: float = 1e-3, 
        epsilon: float = 1e-6,
        noise_var: float = 1e-5,
    ) -> None:
        super().__init__()
        self.eval_fn = eval_fn 
        self.loss_fn = loss_fn
        self.loss_last_fn = default(loss_last_fn, loss_fn)
        self.norm_fn = norm_fn
        self.num_steps = num_steps 
        self.step_size = step_size
        self.epsilon = epsilon 
        self.noise_var = noise_var
        
    def forward(self, embed, state, input_mask,sent=True):
        noise = torch.randn_like(embed.float(), requires_grad=True) * self.noise_var
        
        if sent == True:
          # Indefinite loop with counter 
          for i in count():
            # Compute perturbed embed and states 
            embed_perturbed = embed + noise
            state_perturbed, _ = self.eval_fn(embed_perturbed.long(),input_mask)
            # Return final loss if last step (undetached state)
            if i == self.num_steps:
                return self.loss_last_fn(state_perturbed, state) 
            # Compute perturbation loss (detached state)
            loss = self.loss_fn(state_perturbed, state.detach())
            # Compute noise gradient ∂loss/∂noise
            noise_gradient, = torch.autograd.grad(loss, noise,allow_unused=True)
            # Move noise towards gradient to change state as much as possible 
            # Modify the computation of step to handle NoneType
            if noise_gradient is not None:
                step = noise + self.step_size * noise_gradient
            else:
                # Handle the case where noise_gradient is None, e.g., set step to noise
                step = noise
                
            
            # Normalize new noise step into norm induced ball 
            step_norm = self.norm_fn(step)
            noise = step / (step_norm + self.epsilon)
            # Reset noise gradients for next step
            noise = noise.detach().requires_grad_()
            
            
          
        else:
          for i in count():
              # Compute perturbed embed and states 
              embed_perturbed = embed + noise 
              _,state_perturbed = self.eval_fn(embed_perturbed.long(),input_mask)
              # Return final loss if last step (undetached state)
              if i == self.num_steps: 
                  return self.loss_last_fn(state_perturbed, state) 
              # Compute perturbation loss (detached state)
              loss = self.loss_fn(state_perturbed, state.detach())
              # Compute noise gradient ∂loss/∂noise
              noise_gradient, = torch.autograd.grad(loss, noise,allow_unused=True)
              if noise_gradient is not None:
                  step = noise + self.step_size * noise_gradient
              else:
                  # Handle the case where noise_gradient is None, e.g., set step to noise
                  step = noise  
              # Normalize new noise step into norm induced ball 
              step_norm = self.norm_fn(step)
              noise = step / (step_norm + self.epsilon)
              # Reset noise gradients for next step
              noise = noise.detach().requires_grad_()
        
        # for i in count():
        #     # Compute perturbed embed and states 
        #     embed_perturbed = embed + noise*0.5 + noise2*0.5 
        #     state_perturbed, state_perturbed2 = self.eval_fn(embed_perturbed.long(),input_mask)
        #     # Return final loss if last step (undetached state)
        #     if i == self.num_steps:
        #         return self.loss_last_fn(state_perturbed, state) , self.loss_last_fn(state_perturbed2, state2)
        #     # Compute perturbation loss (detached state)
        #     loss = self.loss_fn(state_perturbed, state.detach())
        #     loss2 = self.loss_fn(state_perturbed2, state2.detach())
        #     # Compute noise gradient ∂loss/∂noise
        #     noise_gradient, = torch.autograd.grad(loss, noise,allow_unused=True)
        #     noise_gradient2, = torch.autograd.grad(loss2, noise2,allow_unused=True)
        #     # Move noise towards gradient to change state as much as possible 
        #     # Modify the computation of step to handle NoneType
        #     if noise_gradient is not None:
        #         step = noise + self.step_size * noise_gradient
        #     else:
        #         # Handle the case where noise_gradient is None, e.g., set step to noise
        #         step = noise
                
        #     if noise_gradient2 is not None:
        #         step2 = noise2 + self.step_size * noise_gradient2
        #     else:
        #         # Handle the case where noise_gradient is None, e.g., set step to noise
        #         step2 = noise2 
            
        #     # Normalize new noise step into norm induced ball 
        #     step_norm = self.norm_fn(step)
        #     noise = step / (step_norm + self.epsilon)
        #     # Reset noise gradients for next step
        #     noise = noise.detach().requires_grad_()
            
        #     step_norm2 = self.norm_fn(step2)
        #     noise2 = step2 / (step_norm2 + self.epsilon)
        #     # Reset noise gradients for next step
        #     noise2 = noise2.detach().requires_grad_()