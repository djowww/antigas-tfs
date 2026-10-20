"""Small removable deep-Q learner for bounded high-level player decisions.

The game client never calls this module. The separate learner process may use
its predictions only after the runner's ordinary safety rules mask actions.
"""
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import random


ACTIONS=('move','hunt')
LAYERS=(12,16,8,2)


def _number(value,default=0.0):
    if value is None:
        return default
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('nonfinite neural observation')
    return float(value)


def _clamp(value,low=0.0,high=1.0):
    return max(low,min(high,value))


def encode_state(state):
    """Encode existing observed facts, never predicted rewards or packets."""
    if not isinstance(state,dict):
        raise ValueError('invalid neural observation')
    health=_number(state.get('health'))
    max_health=max(1.0,_number(state.get('max_health'),1.0))
    floor=_number(state.get('floor'),7.0)
    level=_number(state.get('level'),1.0)
    threats=_number(state.get('nearby_threats'))
    confidence=_number(state.get('route_confidence'))
    return (
        _clamp(health/max_health),
        _clamp((floor-7.0)/4.0,-1.0,1.0),
        _clamp(level/20.0),
        _clamp(threats/8.0),
        _clamp(confidence),
        float(state.get('food_available') is True),
        float(state.get('retreat_available') is True),
        float(state.get('prey_available') is True),
        float(state.get('food_prey_available') is True),
        float(state.get('retreat_required') is True),
        float(state.get('goal')=='hunt'),
        float(state.get('health_band')=='critical'),
    )


class DeepQPolicy:
    hidden_layers=2

    def __init__(self,path=None,*,seed=7,max_replay=4096,learning_rate=.015,gamma=.9):
        if type(max_replay) is not int or not 32<=max_replay<=16384:
            raise ValueError('invalid replay budget')
        if not 0<learning_rate<=.1 or not 0<=gamma<=1:
            raise ValueError('invalid neural learning rate')
        self.path=Path(path) if path else None
        self.rng=random.Random(seed)
        self.learning_rate,self.gamma=learning_rate,gamma
        self.replay=deque(maxlen=max_replay)
        self.weights=[];self.biases=[]
        for width,next_width in zip(LAYERS,LAYERS[1:]):
            radius=math.sqrt(6/(width+next_width))
            self.weights.append([[self.rng.uniform(-radius,radius) for _ in range(width)]
                                 for _ in range(next_width)])
            self.biases.append([0.0]*next_width)
        self.updates=0
        self.target_weights=self._copy_weights()
        self.target_biases=self._copy_biases()
        if self.path and self.path.exists():
            self._load()

    def _copy_weights(self):
        return [[row[:] for row in layer] for layer in self.weights]

    def _copy_biases(self):
        return [layer[:] for layer in self.biases]

    @staticmethod
    def _forward(features,weights,biases,trace=False):
        values=[list(features)]
        for index,(layer,bias) in enumerate(zip(weights,biases)):
            result=[]
            for row,offset in zip(layer,bias):
                value=sum(weight*feature for weight,feature in zip(row,values[-1]))+offset
                result.append(math.tanh(value) if index<len(weights)-1 else value)
            values.append(result)
        return values if trace else values[-1]

    def q_values(self,features):
        if len(features)!=LAYERS[0] or any(not math.isfinite(value) for value in features):
            raise ValueError('invalid neural features')
        return tuple(self._forward(features,self.weights,self.biases))

    def choose(self,state,allowed_actions,rng=None):
        allowed=tuple(action for action in ACTIONS if action in allowed_actions)
        if not allowed:
            # Retreat remains controlled by the deterministic safety layer.
            if tuple(allowed_actions)==('retreat',):
                return 'retreat'
            raise ValueError('no neural safe action')
        rng=rng or self.rng
        if rng.random()<.05:
            return rng.choice(allowed)
        values=self.q_values(encode_state(state))
        return max(allowed,key=lambda action:values[ACTIONS.index(action)])

    def train_example(self,features,action,target):
        if action not in ACTIONS or len(features)!=LAYERS[0] or not math.isfinite(target):
            raise ValueError('invalid neural training example')
        if any(not math.isfinite(value) for value in features):
            raise ValueError('invalid neural features')
        activations=self._forward(features,self.weights,self.biases,trace=True)
        error=activations[-1][ACTIONS.index(action)]-_clamp(target,-5.0,5.0)
        delta=[0.0]*LAYERS[-1]
        delta[ACTIONS.index(action)]=_clamp(error,-1.0,1.0)
        for index in reversed(range(len(self.weights))):
            layer=self.weights[index]
            previous=activations[index]
            if index:
                propagated=[sum(layer[j][i]*delta[j] for j in range(len(delta))) *
                            (1-previous[i]*previous[i]) for i in range(len(previous))]
            for j,row in enumerate(layer):
                for i,value in enumerate(previous):
                    row[i]=_clamp(row[i]-self.learning_rate*delta[j]*value,-4.0,4.0)
                self.biases[index][j]=_clamp(self.biases[index][j]-self.learning_rate*delta[j],-4.0,4.0)
            if index:
                delta=[_clamp(value,-1.0,1.0) for value in propagated]
        self.updates+=1
        if self.updates%200==0:
            self.target_weights=self._copy_weights()
            self.target_biases=self._copy_biases()
        return abs(error)

    def observe(self,state,action,reward,next_state,allowed_next,terminal=False):
        if action not in ACTIONS or type(reward) not in (int,float) or not math.isfinite(reward):
            raise ValueError('invalid neural transition')
        allowed=tuple(candidate for candidate in ACTIONS if candidate in allowed_next)
        features=encode_state(state);following=encode_state(next_state)
        self.replay.append((features,action,_clamp(float(reward),-5.0,5.0),following,
                            allowed,bool(terminal)))
        if len(self.replay)<32:
            return 0
        features,action,reward,following,allowed,terminal=self.replay[
            self.rng.randrange(len(self.replay))]
        future=0.0
        if not terminal and allowed:
            q=self._forward(following,self.target_weights,self.target_biases)
            future=max(q[ACTIONS.index(candidate)] for candidate in allowed)
        self.train_example(features,action,reward+self.gamma*future)
        if self.path and self.updates%200==0:
            self.save()
        return 1

    def save(self):
        if self.path is None:
            return
        payload=dict(version=1,layers=LAYERS,weights=self.weights,biases=self.biases,
                     updates=self.updates)
        encoded=json.dumps(payload,allow_nan=False,separators=(',',':'))
        digest=hashlib.sha256(encoded.encode()).hexdigest()
        wrapper=json.dumps(dict(payload=payload,checksum=digest),allow_nan=False,separators=(',',':'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_name(self.path.name+'.tmp')
        with temporary.open('w',encoding='utf-8') as handle:
            handle.write(wrapper)
            handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,self.path)

    def _load(self):
        try:
            if self.path.stat().st_size>131072:
                raise ValueError('neural checkpoint too large')
            wrapper=json.loads(self.path.read_text(encoding='utf-8'))
            payload=wrapper['payload']
            encoded=json.dumps(payload,allow_nan=False,separators=(',',':'))
            if hashlib.sha256(encoded.encode()).hexdigest()!=wrapper['checksum']:
                raise ValueError('neural checkpoint checksum mismatch')
            if payload['version']!=1 or tuple(payload['layers'])!=LAYERS:
                raise ValueError('invalid neural checkpoint architecture')
            weights,biases=payload['weights'],payload['biases']
            if len(weights)!=3 or len(biases)!=3 or any(
                    len(layer)!=out or len(bias)!=out or any(
                        len(row)!=width or any(type(value) not in (int,float) or
                        not math.isfinite(value) or abs(value)>4 for value in row)
                        for row in layer) or any(type(value) not in (int,float) or
                        not math.isfinite(value) or abs(value)>4 for value in bias)
                    for layer,bias,width,out in zip(weights,biases,LAYERS,LAYERS[1:])):
                raise ValueError('invalid neural checkpoint weights')
            updates=payload['updates']
            if type(updates) is not int or updates<0:
                raise ValueError('invalid neural checkpoint updates')
        except (OSError,KeyError,TypeError,json.JSONDecodeError,OverflowError) as exc:
            raise ValueError('invalid neural checkpoint') from exc
        self.weights=weights;self.biases=biases;self.updates=updates
        self.target_weights=self._copy_weights();self.target_biases=self._copy_biases()
