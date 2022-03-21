# -*- coding: utf-8 -*-
"""
Created on Wed Dec  1 12:11:39 2021

adapted for personal use from base code written by
modified from code of user jondila at:
    https://github.com/basler/pypylon/issues/425

changes include:
    - Variable camera number support
    - implemented a 2-by-x window layout with even spacing
    - camera release upon stopping of Live view and closing of window
    - Emulation camera fill-in for when no cameras are present
    - OOP implementation
    
to be added:
    - framerate display and setting
    

@author: nicnag
"""

from pypylon import pylon
from pypylon import genicam
from PIL import Image
from PIL import ImageTk
import tkinter as tk
import threading

import cv2
import os
import time

class App():
    #Class constructor init
    #configures window positions, initialise parameters and adds functionality from other methods
    def __init__(self):
        
        maxcams = 5
        
        #initialise parameters used throughout this class
        self.camera = [0 for i in range(maxcams)] 
        self.converter = [0 for i in range(maxcams)] 
        self.PixelFormat = [0 for i in range(maxcams)] 
        self.image = [0 for i in range(maxcams)] 
        self.CamIdx = [0 for i in range(maxcams)] 
        self.bCamOpen = [False for i in range(maxcams)] 
        self.bLiveThread = [False for i in range(maxcams)] 
        self.panel = [0 for i in range(maxcams)]
        self.initialised = False
        
        #number of cameras and window configuration
        self.maxcams = maxcams
        self.window = tk.Tk()
        self.window.title('Multicam_show')
        
        #window sizing and side padding values
        self.wx = 600
        self.wy = 400
        self.padval = 50
        #calculate the number of panels in window
        if self.maxcams%2==1:
            self.wnumber = self.maxcams+1
        else:
            self.wnumber = self.maxcams
        
        self.xspacing = self.padval*2/((self.wnumber/2)+1)
        self.yspacing = self.padval*2/(2+1)
        
        self.lastbtny = self.wy*2 + (2.7*self.yspacing)
        self.lastbtnx = (round(self.wnumber/2))*self.wx + (round(self.wnumber/2)*self.xspacing)
        
        geomstr = str(round(self.wnumber/2)*self.wx+(self.padval*2))+'x'+str(self.wy*2+(self.padval*2))
        self.window.geometry(geomstr+'+10+10')
       
        #window text labels
       
        self.frameobj = [tk.StringVar() for i in range(maxcams)]
        self.frameobj = [self.frameobj[i].set('framerate = ' + 'xx/s') for i in range(maxcams)]

        self.expobj = [tk.StringVar() for i in range(maxcams)]
        self.expobj = [self.expobj[i].set('default') for i in range(maxcams)]
        
        self.serialobj = [tk.StringVar() for i in range(maxcams)]
        self.serialobj = [self.serialobj[i].set('Camera serial no. : ' + 'xxxx') for i in range(maxcams)]
                
        
        self.framerate_labels = [tk.Label(self.window, textvariable = self.frameobj[i]) for i in range(maxcams)]
        self.camexposure_labels = [tk.Label(self.window, textvariable = self.expobj[i]) for i in range(maxcams)]
        self.camserial_labels = [tk.Label(self.window, textvariable = self.serialobj[i]) for i in range(maxcams)]
        
        #placing labels
        
        
        #different types of buttons
        #press buttons
 
        self.btnInitCam = tk.Button(self.window, text = 'InitCam', command = self.InitCam)
        self.btnInitCam.grid(row = 0,column = 2, sticky = 'W')
        self.btnInitCam.place(x = self.lastbtnx-140, y = self.lastbtny,anchor = 'e')
        
        self.btnStartLive = tk.Button(self.window, text = 'StartLive', command = self.LiveStart)
        self.btnStartLive.grid(row = 0,column = 2, sticky = 'W')
        self.btnStartLive.place(x = self.lastbtnx-70, y = self.lastbtny,anchor = 'e')
        
        self.btnStopLive = tk.Button(self.window, text = 'StopLive', command = self.LiveStop)
        self.btnStopLive.grid(row = 0,column = 2, sticky = 'W')
        self.btnStopLive.place(x = self.lastbtnx, y = self.lastbtny,anchor = 'e')
        
        #define what to do when window close
        self.window.protocol('WM_DELETE_WINDOW',self.on_closing)
        self.window.mainloop()
        
        
    def InitCam(self):
        
        self.initialised = True
        #sets number of emulation devices to 0 prior to device count
        os.environ['PYLON_CAMEMU'] = str(0)
        
        try:
            self.tlf = pylon.TlFactory.GetInstance()#gets transport layer
            self.devices = self.tlf.EnumerateDevices()#extract devices
    
            if len(self.devices)<self.maxcams:
                os.environ['PYLON_CAMEMU'] = str(self.maxcams-len(self.devices))#pads with emulation devices
            
                #redefines transport layer and devices
                self.tlf = pylon.TlFactory.GetInstance()
                self.devices = self.tlf.EnumerateDevices()
            
            for i in range(self.maxcams):
                if self.bCamOpen[i]==False:
                    self.camera[i] = pylon.InstantCamera(self.tlf.CreateDevice(self.devices[i]))
                    print('Using device ','CAM: ', self.camera[i].GetDeviceInfo().GetModelName(),self.camera[i].GetDeviceInfo().GetSerialNumber())
                    self.camera[i].Open()
                    self.bCamOpen[i] = True
                    print('Cam',i,': open')
                    self.PixelFormat[i] = self.camera[i].PixelFormat.GetValue()
                    self.converter[i] = pylon.ImageFormatConverter()
            
                if self.PixelFormat[i] =='Mono8':
                    self.converter[i].OutputPixelFormat = pylon.PixelType_Mono8
                else:
                    self.conferter[i].OutputPixelFormat = pylon.PixelType_BGR8packed
            
                self.converter[i].OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
            
        except genicam.GenericException as e:
            print('An exception occured.', str(e))
            exitCode = 1
                
    def LiveThread(self,StrIdx):
        i = int(StrIdx)
        try:
            #predefine params
            self.panel[i] = None
            self.image[i] = []
            
            #start grabbing
            self.camera[i].StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            print('Cam',i,': Start Grabbing')
            
            while self.bLiveThread[i]:
                grabResult = self.camera[i].RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                
                if self.devices[i].GetModelName()=='Emulation':
                    live_framerate = self.camera[i].ResultingFrameRateAbs.GetValue()
                    # self.frameobj.set('framerate = '+str(round(live_framerate)) +'/s')
                else:
                    live_framerate = self.camera[i].ResultingFrameRate.GetValue()
                    # self.frameobj.set('framerate = '+str(round(live_framerate)) +'/s')
                    
                if grabResult.GrabSucceeded():
                    self.image[i] = self.converter[i].Convert(grabResult)
                    self.image[i] = self.image[i].GetArray()
                    
                    if self.image[i] is not []:
                        self.image[i] = cv2.cvtColor(self.image[i],cv2.COLOR_BGR2RGB)
                        self.image[i] = cv2.resize(self.image[i], (600,400))
                        self.image[i] = ImageTk.PhotoImage(image = Image.fromarray(self.image[i]))
                        
                        if self.panel[i] is None:
                            self.panel[i] = tk.Label(image=self.image[i])
                            self.panel[i].image = self.image[i]
                            self.panel[i].pack(side = 'left')
                            
                            if i%2==0:
                            #if this is the first even numbered camera
                                if i<1:
                                    #place at first position
                                    self.panel[i].place(x = self.xspacing, y=self.yspacing)
                                    #if this is not the first even camera
                                elif i>1:
                                    self.panel[i].place(x= (i/2)*self.wx + (i/2+1)*self.xspacing, y=self.yspacing)
                                    #if cameras are odd put them in the second
                            else:
                                #if this is the first odd numbered camera
                                if i<2:
                                    self.panel[i].place(x=self.xspacing, y=self.yspacing*2+self.wy)
                                    #otherwise subsequent odd camera panel position is determined by:
                                elif i>2:
                                    self.panel[i].place(x=(i-1)/2*self.wx + ((i-1)/2+1)*self.xspacing ,y = self.yspacing*2+self.wy) 
                        else:
                            self.panel[i].configure(image=self.image[i])
                            self.panel[i].image = self.image[i]
                else:
                    print('Error: ', grabResult.ErrorCode)
                
                grabResult.Release()
                    
        except genicam.GenericException as e:
            print('An exception occurred.', str(e))
                            
                    
                
                
            
    def LiveStart(self):
        for i in range(self.maxcams):
            if self.bLiveThread[i] == False:
                cam_LiveThread = threading.Thread(target=self.LiveThread,args=(str(i)))
                cam_LiveThread.daemon = True
                self.bLiveThread[i] = True
                cam_LiveThread.start()
            
        
    def LiveStop(self):
        
        for i in range(self.maxcams):
            if self.bLiveThread[i]==True:
                self.bLiveThread[i] = False
                time.sleep(0.05)
                self.camera[i].StopGrabbing()
                print('Cam',i,': stop grabbing')
                self.camera[i].Close()
                print('Cam',i,': camera closed')
        
    def on_closing(self):
               
        self.window.destroy()
        
        if self.initialised==True:
        
            for i in range(self.maxcams):
                if self.bLiveThread[i]==True:
                    self.bLiveThread[i] = False
                    time.sleep(0.05)
                if self.camera[i].IsGrabbing:
                    self.camera[i].StopGrabbing()
                    print('Cam',i,': stop grabbing')
                if self.camera[i].IsOpen():
                    self.camera[i].Close()
                    print('Cam',i,': closed')   
        
    
#runs app using tkinter window for 5 cameras with the window title of multicam_show
a = App()
        

        
        
        
        