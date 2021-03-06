import os
import numpy as np
import torch
import torch.optim as optim
import torch.utils.data as data

from model import *
from metric import accuracy
from config import get_args
args = get_args()

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

train_tensor, train_label = torch.load(args.train_path)
valid_tensor, valid_label = torch.load(args.valid_path)
test_tensor, test_label = torch.load(args.test_path)
train_tensor = train_tensor.to(device)
valid_tensor = valid_tensor.to(device)
test_tensor = test_tensor.to(device)
train_label = train_label.to(device)
valid_label = valid_label.to(device)
test_label = test_label.to(device)
train_loader = data.DataLoader(data.TensorDataset(train_tensor, train_label),
                               batch_size=args.batch_size, shuffle=False)
valid_loader = data.DataLoader(data.TensorDataset(valid_tensor, valid_label),
                               batch_size=args.batch_size, shuffle=False)
test_loader = data.DataLoader(data.TensorDataset(test_tensor, test_label),
                              batch_size=args.batch_size, shuffle=False)


'''
"keypoints": {
    0: "nose",
    1: "left_eye",
    2: "right_eye",
    3: "left_ear",
    4: "right_ear",
    5: "left_shoulder",
    6: "right_shoulder",
    7: "left_elbow",
    8: "right_elbow",
    9: "left_wrist",
    10: "right_wrist",
    11: "left_hip",
    12: "right_hip",
    13: "left_knee",
    14: "right_knee",
    15: "left_ankle",
    16: "right_ankle"
},
"skeleton": [
    [16,14],[14,12],[17,15],[15,13],[12,13],[6,12],[7,13], [6,7],[6,8],
    [7,9],[8,10],[9,11],[2,3],[1,2],[1,3],[2,4],[3,5],[4,6],[5,7]]
'''
A = [[0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [1, 1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0],
     [0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0],
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0],
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1],
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
     [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0]]
A = torch.from_numpy(np.asarray(A)).to(device)

model = GGCN(A, train_tensor.size(3), args.num_classes,
             [train_tensor.size(3), train_tensor.size(
                 3)*3], [train_tensor.size(3)*3, 16, 32, 64],
             args.feat_dims, args.dropout_rate)
if device == 'cuda':
    model.cuda()

num_params = 0
for p in model.parameters():
    num_params += p.numel()
print(model)
print('The number of parameters: {}'.format(num_params))

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=args.learning_rate,
                       betas=[args.beta1, args.beta2], weight_decay=args.weight_decay)
scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=20, gamma=0.1)

best_epoch = 0
best_acc = 0


def train():
    global best_epoch, best_acc

    if args.start_epoch:
        model.load_state_dict(torch.load(os.path.join(args.model_path,
                                                      'model-%d.pkl' % (args.start_epoch))))

    # Training
    for epoch in range(args.start_epoch, args.num_epochs):
        train_loss = 0
        train_acc = 0

        model.train()
        for i, (x, target) in enumerate(train_loader, start=1):
            logit = model(x.float())

            loss = criterion(logit, target)

            model.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            train_acc += accuracy(logit, target)
        scheduler.step()

        print('[epoch', epoch+1, '] Train loss:',
              train_loss/i, 'Train Acc:', train_acc/i)

        if (epoch+1) % args.val_step == 0:
            model.eval()
            val_loss = 0
            val_acc = 0
            with torch.no_grad():
                for i, (x, target) in enumerate(valid_loader, start=1):
                    logit = model(x.float())

                    val_loss += criterion(logit, target).item()
                    val_acc += accuracy(logit, target)

                if best_acc <= (val_acc/i):
                    best_epoch = epoch+1
                    best_acc = (val_acc/i)
                    torch.save(model.state_dict(), os.path.join(
                        args.model_path, 'model-%d.pkl' % (best_epoch)))

            print('Val loss:', val_loss/i, 'Val Acc:', val_acc/i)


def test():
    global best_epoch

    model.load_state_dict(torch.load(os.path.join(args.model_path,
                                                  'model-%d.pkl' % (best_epoch))))
    print("load model from 'model-%d.pkl'" % (best_epoch))

    model.eval()
    test_loss = 0
    test_acc = 0
    with torch.no_grad():
        for i, (x, target) in enumerate(test_loader, start=1):
            logit = model(x.float())
            #print(F.softmax(logit, 1).cpu().numpy(), torch.max(logit, 1)[1].float().cpu().numpy())

            test_loss += criterion(logit, target).item()
            test_acc += accuracy(logit, target)

    print('Test loss:', test_loss/i, 'Test Acc:', test_acc/i)


if __name__ == '__main__':
    if args.mode == 'train':
        train()
    elif args.mode == 'test':
        best_epoch = args.test_epoch
    test()
