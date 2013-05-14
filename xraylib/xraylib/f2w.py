#
# f2w-package by V. Honkim\"aki
#
# Copyright 2012 European Synchrotron Ratiation Facility
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

#  example:
#   >>> import edf                # or however you load the edf-files
#   >>> import f2w                # import the detector classes
#   >>> Det=f2w.Pixium()          # object for the Pixium detector
#   >>> print(Det)                # ...just to see what parameters it holds
#   >>> P=edf.read("pix.edf")     # reading the 2d pattern from the edf-file
#   >>> Det.calibrate(P,[10,130]) # calibrating the center and the tilt using
#                                 # all the data between 10mm < radius < 130mm
#   >>> r,A=Det.integrate(P,1)    # integrates over the whole 2pi
#   >>> r,A=Det.integrate(P,N)    # integrates N pies
#
from numpy import zeros, pi, meshgrid, arange, sqrt, arctan2, isnan, floor, prod,\
                  trunc, nonzero, diff, hstack, vstack, int_, transpose, linalg, \
                  dot, sin, cos, cumsum, ones

import utils

class Detector(object):
    _T = []
    _R = []
    _dr = []
    _updated   = False
    """A general detector object"""
    def __init__(self, **kwargs):
        for key in kwargs:
            if key in ['distance','tilt', 'origin']:
                self.__dict__.update({'_%s' % key : utils.toFloat(kwargs[key])})
    def setdist(self,D):
       self._distance = D; self._updated = False;
    def setorigin(self,v):
       self._origin = v; self._updated = False;
    def settilt(self,v):
       self._tilt = v; self._updated = False;
    def __str__(self):
       s = 'Distance = ' + repr(self._distance) + 'mm\nOrigin   = ' + repr(self._origin) \
         + 'mm\nTilt     = ' + repr(self._tilt) + 'deg\nPixels   = ' + repr(self._pixels)\
         + '\nPixsize  = ' + repr(self._pixelsize) + 'mm';
       return(s)
    def _calcrt(self):
        if (not self._updated):
           r = pi/180.0/self._distance
           a = self._tilt[0]*r; b = self._tilt[1]*r;
           xv = arange(self._pixels[1])*self._pixelsize[1]-self._origin[1]
           yv = arange(self._pixels[0])*self._pixelsize[0]-self._origin[0]
           x,y = meshgrid(xv,yv)
           self._R = sqrt(x**2+y**2)*(1.0-a*y-b*x); self._T = arctan2(y,x); self._updated = True
           self._R.shape = prod(self._R.shape); self._T.shape = prod(self._T.shape);
           self._Rind = self._R.argsort(axis=None);
           n = cumsum(ones(self._Rind.shape));
           self._dr = sqrt(self._pixelsize[0]*self._pixelsize[1])
           i = floor(self._R[self._Rind]/self._dr + 0.5)
           self._jind = 0 < diff(i);
           self._nR = i[self._jind]*self._dr;
           self._dcj = diff(hstack((0,n[self._jind])))
    def integrate(self,Im,n=1):
       if (not self._updated):
          self._calcrt();
       Imc = Im[:]; Imc.shape = prod(Imc.shape);
       if n>1:
           R = self._R[:]; T = self._T[:]; dr = self._dr;
           tpi = 2.0*pi; dp = tpi/n; ip = int_(floor(T/dp+0.5)%n); A = zeros([0,n]);
           for i in range(n):
              j = nonzero(ip == i); a = self._pie(Imc[j],R[j],dr); M = a.shape[0]; m = A.shape[0];
              if (m < M):
                 A = vstack((A,zeros([M-m,n])))
              a.shape = M; A[:M,i] = a;
       else:
           A = zeros(self._nR.shape); c = Imc[self._Rind].cumsum()[self._jind];
           A[0] = c[0]; A[1:] = diff(c); A = A/self._dcj;
       return(self._nR,A);

    def _pie(self,Im,R,dr):
       mn = prod(Im.shape); j = R.argsort(axis=None); w = R[j]/dr;
       ir = int_(w); w0 = 1.0+ir-w; w1 = 1.0-w0; c0 = w0*Im[j]; c1 = w1*Im[j];
       i = isnan(Im[j]); w0[i] = 0; w1[i] = 0; c0[i] = 0; c1[i] = 0;
       w0 = w0.cumsum(); w1 = w1.cumsum(); c0 = c0.cumsum(); c1 = c1.cumsum();
       i = nonzero(diff(ir)); m = ir[-1]+2; A = zeros([m,1]); C = zeros([m,1]);
       ta = diff(hstack((0,c0[i]))); tc = diff(hstack((0,w0[i]))); j = ir[i]; A[j,0] = ta; C[j,0] = tc;
       ta = diff(hstack((0,c1[i]))); tc = diff(hstack((0,w1[i]))); j += 1; A[j,0] += ta; C[j,0] += tc;
       j = nonzero(C); A[j] = A[j]/C[j]; return(A);
    def calibrate(self,Im,rg):
       """
           N  - number of pies
           db - covariance matrix of

           """
       D = self._distance; stp = 1; loops = 0; N = 36; dp = 2*pi/N; p = arange(N)*dp-dp/2;
       y = zeros([N,1]); z = zeros([N,1]); dy = zeros([N,1]); dz = zeros([N,1]);
       sc = 2*pi/sqrt(self._pixelsize[0]*self._pixelsize[1]);
       while ((0.1 < stp) and (loops < 30)):
          r,A = self.integrate(Im,N); i = nonzero((rg[0] < r)*(r < rg[1]))[0]; r = r[i,:]; A = A[i,:];
          d = diff(A[:,-1])/diff(r); C = vstack((A[:-1,-1],d,d*r[-1:]**2/D)).T;
          for j in range(N):
             w = sc*r[:-1]/(A[:-1,j]+1); Cs = (C*w[:,[0,0,0]]).T; db = linalg.inv(dot(Cs,C));
             b = dot(db,dot(Cs,A[:-1,j])); y[j] = b[1]/b[0]; z[j] = b[2]/b[0];
             c = hstack((1,-y[j]))/b[0]; c.shape = [1,2]; dy[j] = dot(c,dot(db[[1,0],:][:,[1,0]],c.T));
             c = hstack((1,-z[j]))/b[0]; c.shape = [1,2]; dz[j] = dot(c,dot(db[[2,0],:][:,[2,0]],c.T));
             d = diff(A[:,j])/diff(r); C = vstack((A[:-1,j],d,d*r[:-1]**2/D)).T;
          y = y/dp; z = z/dp; dy = dy/dp**2; dz = dz/dp**2; C = vstack((cos(p),-sin(p))).T;
          w = (1/dy); Cs = (C*w[:,[0,0]]).T; db = linalg.inv(dot(Cs,C)); c = dot(db,dot(Cs,y));
          stp = sum(c**2); q = c/stp; stp = stp/abs(dot(dot(q.T,db),q)); c.shape = 2;
          utils.debug_print(db=db, normalizer=dot(dot(q.T,db),q))
          self.setorigin(self._origin - c); C = vstack((cos(p),-sin(p))).T; w = (1/dz);
          Cs = (C*w[:,[0,0]]).T; db = linalg.inv(dot(Cs,C)); c = dot(db,dot(Cs,z));
          stp2 = sum(c**2); q = c/stp2; stp2 = stp2/abs(dot(dot(q.T,db),q)); c.shape = 2;

          utils.debug_print(Cs=Cs,c=c,db=db,stp=stp,stp2=stp2)

          self.settilt(self._tilt - c*180/pi); stp = sqrt(stp+stp2); loops += 1;
          print("Step = {0:.3f}".format(stp[0,0]))

class Pixium(Detector):
    """Pixium detector object"""
    def __init__(self, **kwargs):
       """ Set up default geometry and
           allow it to be overriden in base __init__ """
       self._distance  = 1000
       self._origin    = [147.84,203.28]
       self._tilt      = [0,0]
       self._pixels    = [1920,2640]
       self._pixelsize = [0.154,0.154]
       super(Pixium,self).__init__(**kwargs)

class Perkin(Detector):
    """ detector object"""
    def __init__(self, **kwargs):
       self._distance  = 1000
       self._origin    = [204.8,204.8]
       self._tilt      = [0,0]
       self._pixels    = [2048,2048]
       self._pixelsize = [0.200,0.200]
       super(Perkin,self).__init__(**kwargs)

def get_detector(name, **kwargs):
    """ Detector name to object translation.
        Based on similar method in pyFAI.  """
    detectors = {"perkin": Perkin,
                 "pixium": Pixium, }
    _name = name.lower()
    if _name in detectors:
        return detectors[_name](**kwargs)
    else:
        raise Exception('Detector %s not known.' % (name,))

class Calibrator(object):
    def __init__(self, image, detector):
        self.image = image
        self.detector = detector

    def calibrate(self, lower=10, upper=350, threshold=100):
        """ Calibrate tilt and origin of detector using data in the interval
        [@lower,@upper]mm with a value exceeding @threshold. """
        image = self.image
        image[image<threshold] = 0
        self.detector.calibrate(image,[lower,upper])

    def __str__(self):
        return str(self.detector)
