# sPytfire

sPytfire is the sensor payload software for the University of Bristol's MACE project, which aims to fly UAVs through passively degassing volcanic plumes to measure particle sizes, radiative fluxes and volcanic SO2.

## Expected Hardware 
The software operates on Raspberry Pi Zero W2 or Compute Module 5, and connects to all scientific sensors deployed by the project. Expected connections to the UAV are serial port communications with the flight controller and power from the UAV batteries. Currently incorperated modules are:

MAVLINK
Analogue longwave and shortwave radiative flux sensors
Optical Particle Counter
Direct and Diffuse Pyronometer
Temperature, Pressure and Humidity Sensor
10-channel Spectrometer (to be upgraded to UV Spectrometer)
Internal voltage Sensor

## Install
### Creating the python virtual environment
The Raspberry Pi prevents direct installation of dependancies into the default python path. We create a virtual environment to run the python code for the Raspberry Pi Compute Module 5.
```
sudo apt install -y python3-venv python3-full
python3 -m venv sensor
```
Some Raspberry Pi models have insufficient memory to directly install Pyside6. A variation is required to download Pyside6 first, then create the python environment
```
sudo apt install python3-pyside6.qtcore python3-pyside6.qtwidgets
python3 -m venv --system-site-packages sensor
```
### Install dependancies
sPytfire requires 'numpy' for numerical calculations
```
pip install numpy

#raspberry pi virtual environment needs additional modules to run adafruit
pip install RPi.GPIO #!WARNING. I had some issues with this for the compute module.

#check sensors have been correctly mounted using:
sudo i2cdetect -y 1

#install packages to run the BME280
pip install pimoroni-bme280

#Need to install pymavlink
pip install --upgrade pymavlink
```
A useful command to check i2c connections is as follows:
```
sudo i2cdetect -y 1
```