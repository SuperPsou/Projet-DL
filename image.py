# -*- coding: utf-8 -*-
"""Image

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1aEZAsoZ71v4XMVUCaYj47xG2Yzxl9KiJ

## Import
"""

import torch

from torch.utils.data import dataloader
from torch.utils.data import Dataset

import torchvision.transforms as transforms

from PIL import Image

import pandas as pd

from typing import Any, Callable, Optional, Tuple

#!pip install transformers
#!pip install datasets
#!pip install sentencepiece

import torch
torch.__version__

"""## Load Data"""

class VQADataset(Dataset):
  """
    This class loads a shrinked version of the VQA dataset (https://visualqa.org/)
    Our shrinked version focus on yes/no questions. 
    To load the dataset, we pass a descriptor csv file. 
    
    Each entry of the csv file has this form:

    question_id ; question_type ; image_name ; question ; answer ; image_id

  """
  def __init__(self, path : str, dataset_descriptor : str, image_folder : str, transform : Callable) -> None:
    """
      :param: path : a string that indicates the path to the image and question dataset.
      :param: dataset_descriptor : a string to the csv file name that stores the question ; answer and image name
      :param: image_folder : a string that indicates the name of the folder that contains the images
      :param: transform : a torchvision.transforms wrapper to transform the images into tensors 
    """
    super(VQADataset, self).__init__()
    self.descriptor = pd.read_csv(path + '/' + dataset_descriptor, delimiter=';')
    self.path = path 
    self.image_folder = image_folder
    self.transform = transform
    self.size = len(self.descriptor)
  
  def __len__(self) -> int:
    return self.size

  def __getitem__(self, idx : int) -> Tuple[Any, Any, Any]:
    """
      returns a tuple : (image, question, answer)
      image is a Tensor representation of the image
      question and answer are strings
    """
    
    image_name = self.path + '/' + self.image_folder + '/' + self.descriptor["image_name"][idx]

    image = Image.open(image_name).convert('RGB')

    image = self.transform(image)

    question = self.descriptor["question"][idx]

    answer = self.descriptor["answer"][idx]

    return (image, question, answer)


from torch.utils.data import DataLoader

# Précisez la localisation de vos données sur Google Drive
path = "/home/equipe2/harispe"
image_folder = "boolean_answers_dataset_images_10000"
descriptor = "boolean_answers_dataset_10000.csv"


batch_size = 2

# exemples de transformations
transform = transforms.Compose(
    [
     transforms.Resize((224,224)),   #TOUTES LES IMAGES 224/224
     transforms.ToTensor(),     
     transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
    ]
)

vqa_dataset = VQADataset(path, descriptor, image_folder, transform=transform)


vqa_dataloader = DataLoader(vqa_dataset,batch_size=batch_size, shuffle=True, num_workers=0)

"""## Preparation Test + Train et "yes" -> 0 "no" -> 1"""

from transformers import AutoTokenizer, AutoModelForSequenceClassification

# List of pretrained models: https://huggingface.co/models?filter=text-classification
tokenizer_albert = AutoTokenizer.from_pretrained("textattack/albert-base-v2-yelp-polarity")
model_albert = AutoModelForSequenceClassification.from_pretrained("textattack/albert-base-v2-yelp-polarity")

"""###Préparation des données :"""

taille = vqa_dataset.__len__()
trainPercent = 0.8
tailleTrain = (int)(trainPercent * taille)

trainSet = []
testSet = []
question_set = []


for i in range(taille):

  ####### OUTPUT Transforme : Yes -> 0   No -> 1
  output = 1
  if vqa_dataset.__getitem__(i)[2] == "yes":
    output = 0


  ####### IMAGE
  image = vqa_dataset.__getitem__(i)[0]

  #Taille image : 3*224*224


  ####### QUESTION extrait les donnée à l'aide de token + albert model

  question = vqa_dataset.__getitem__(i)[1]

  test_token = tokenizer_albert(question)

  #Informations du token
  input_ids = torch.LongTensor([test_token['input_ids'],test_token['token_type_ids']])
  token_type_ids = torch.LongTensor(test_token['token_type_ids'])
  attention_mask = torch.FloatTensor(test_token['attention_mask'])


  value = model_albert.forward(input_ids=input_ids , token_type_ids=token_type_ids, output_hidden_states = True)
  hidden_states = value[1]

  #On recupere la deniere "hidden_state" du model albert
  last_layer = hidden_states[-1]

  #On reforme les donnée pour etre utilisable
  last_layer = torch.cat((last_layer[0], last_layer[1]), 1)
  while len(last_layer)<16:
    last_layer = torch.cat(  (  last_layer , torch.empty(1,1536)  )  ,0)

  question = last_layer 
  #Forme finale de la question : 16*1536


  ####### TRAIN ET TEST SET
  if i<tailleTrain:
    trainSet.append([image,question,output])
  else:
    testSet.append([image,question,output])

print("Taille entrainement :",len(trainSet))

trainloader = torch.utils.data.DataLoader(trainSet, batch_size=10, shuffle=True)
testloader = torch.utils.data.DataLoader(testSet, batch_size=10, shuffle=False)

print(trainloader)

"""## Modele"""

import torch.nn.functional as F

class LeNet5(torch.nn.Module):
  
  def __init__(self, D_out):
    super(LeNet5, self).__init__()

    #Traitement image
    self.conv1     = torch.nn.Conv2d(in_channels=3, out_channels=6, kernel_size=(5,5), stride=1, padding=2)
    self.avg_pool1 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv2     = torch.nn.Conv2d(in_channels=6, out_channels=16, kernel_size=(5,5), stride=1)
    self.avg_pool2 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv3     = torch.nn.Conv2d(in_channels=16, out_channels=120, kernel_size=(5,5), stride=1) 
    self.avg_pool3 = torch.nn.AvgPool2d(kernel_size=(2,2), stride=2)
    self.conv4     = torch.nn.Conv2d(in_channels=120, out_channels=240, kernel_size=(5,5), stride=1)
    self.flatten   = torch.nn.Flatten() #multipli tout   240*21*21

    #Traitement image
    self.linear1   = torch.nn.Linear(240*21*21, 200)

    #Traitement question
    self.linear3   = torch.nn.Linear( 16*1536 , 200)

    #Fusion Traitement
    self.linear2   = torch.nn.Linear( 200+200, D_out)

  def forward(self, x,y):
    
    x = F.relu(self.conv1(x) )
    x = self.avg_pool1(x)
    x = F.relu( self.conv2(x) )
    x = self.avg_pool2(x)
    x = F.relu( self.conv3(x) )
    x = self.avg_pool3(x)
    x = F.relu( self.conv4(x) )


    y = self.flatten(y) #16*1536
    x = self.flatten(x) #240*21*21


    x = F.relu( self.linear1(x) )
    y = F.relu( self.linear3(y) )


    z = torch.cat((x, y), 1)
    z = self.linear2(z)
    
    return z

def train_optim(model, epochs, log_frequency, device, learning_rate=1e-4):

  model.to(device) 

  loss_fn = torch.nn.CrossEntropyLoss(reduction='mean')
  optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
  
  for t in range(epochs):

      model.train()

      for batch_id,  batch in enumerate(trainloader) : 

        images, questions, labels  = batch

        questions = torch.FloatTensor(questions)
        questions = questions.to(device)
        images = images.to(device)
        labels = torch.LongTensor(labels)
        labels = labels.to(device)

        # FORWARD
        y_pred = model(images,questions)

        loss = loss_fn(y_pred, labels)

        if batch_id % log_frequency == 0:
            print("epoch: {:03d}, batch: {:03d}, loss: {:.3f} ".format(t+1, batch_id+1, loss.item()))

        optimizer.zero_grad()
        loss.backward(retain_graph=True)
        optimizer.step()

      #ACCURACY Calcul
      model.eval()
      total = 0
      correct = 0
      for batch_id, batch in enumerate(testloader):
        images ,questions, labels = batch
        images , labels = images.to(device), labels.to(device)
        y_pred = model(images,questions)
        sf_y_pred = torch.nn.Softmax(dim=1)(y_pred) # softmax
        _, predicted = torch.max(sf_y_pred , 1)     # decision rule, max
        
        total += labels.size(0)
        correct += (predicted == labels).sum().item()
      
      print("[validation] accuracy: {:.3f}%\n".format(100 * correct / total))

"""## Lance modele"""

D_out = 2

model = LeNet5(D_out)

## Select the device
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

## train the model
train_optim(model, epochs=10, log_frequency=60, device=device, learning_rate=1e-4)
