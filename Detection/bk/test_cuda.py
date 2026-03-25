import torch

print("torch version:", torch.__version__)
print("cuda available:", torch.cuda.is_available())
print("torch cuda version:", torch.version.cuda)
if torch.cuda.is_available():
    print("gpu name:", torch.cuda.get_device_name(0))