from typing import Dict, Tuple, List, Callable

import jax.numpy as tensor
from jax import grad, jit
from jax import random
from tqdm import tqdm

from dnet.data import BatchIterator
from dnet.layers import FC


class Optimizer:

    def __init__(self, layers: List[FC], loss: Callable, accuracy: Callable, epochs: int, lr: float,
                 bs: int = 32) -> None:
        self.layers: List[FC] = layers
        self.loss_fn: Callable = loss
        self.accuracy_fn: Callable = accuracy
        self.epochs: int = epochs
        self.lr: float = lr
        self.iterator = BatchIterator(batch_size=bs)
        self.grad_fn: Callable = jit(grad(self.compute_cost))
        self.network_params: List[Dict[str, tensor.array]] = []
        self.cost: List[float] = []
        self.accuracy: List[float] = []

    def train(self, inputs: tensor.array, outputs: tensor.array) -> None:
        raise NotImplementedError

    def init_network_params(self, input_shape: Tuple[int, int]) -> None:
        key: tensor.array = random.PRNGKey(0)
        subkey: tensor.array
        for i, layer in enumerate(self.layers):
            key, subkey = random.split(key)
            weight_shape: Tuple[int, int] = (layer.units, self.layers[i - 1].units if i != 0 else input_shape[0])
            w: tensor.array = random.normal(subkey, shape=weight_shape) * 0.01
            b: tensor.array = tensor.zeros(shape=(layer.units, 1))
            self.network_params.append({"w": w, "b": b})

    def compute_predictions(self, params: List[Dict[str, tensor.array]], inputs: tensor.array) -> tensor.array:
        a: tensor.array = inputs
        for i, layer in enumerate(self.layers):
            z: tensor.array = tensor.dot(params[i].get("w"), a) + params[i].get("b")
            a = layer.activation(z)
        return a

    def compute_cost(self, params: List[Dict[str, tensor.array]], inputs: tensor.array, outputs: tensor.array) -> float:
        predictions: tensor.array = self.compute_predictions(params, inputs)
        return self.loss_fn(predictions, outputs)

    def compute_accuracy(self, predictions: tensor.array, outputs: tensor.array) -> float:
        return self.accuracy_fn(predictions, outputs)

    def evaluate(self, inputs: tensor.array, outputs: tensor.array) -> float:
        predictions = self.compute_predictions(self.network_params, inputs)
        return self.compute_accuracy(predictions, outputs)


class SGD(Optimizer):

    def train(self, inputs: tensor.array, outputs: tensor.array) -> None:
        super().init_network_params(inputs.shape)
        for _ in tqdm(range(self.epochs), desc="Training the model"):
            loss: float = 0.0
            for batch in self.iterator(inputs, outputs):
                grads: List[Dict[str, tensor.array]] = self.grad_fn(self.network_params, batch.inputs, batch.outputs)
                for i, layer_params in enumerate(grads):
                    self.network_params[i]["w"] -= self.lr * layer_params.get("w")
                    self.network_params[i]["b"] -= self.lr * layer_params.get("b")
                loss += self.compute_cost(self.network_params, batch.inputs, batch.outputs)
            self.cost.append(loss)
            self.accuracy.append(self.evaluate(inputs, outputs))


class Momentum(Optimizer):

    def __init__(self, layers: List[FC], loss: Callable, accuracy: Callable, epochs: int, lr: float,
                 bs: int = 32, beta: float = 0.9):
        super().__init__(layers, loss, accuracy, epochs, lr, bs)
        self.beta: float = beta

    def init_network_params(self, input_shape: Tuple[int, int]) -> None:
        super().init_network_params(input_shape)
        self.momentum_params: List[Dict[str, tensor.array]] = [
            {"w": tensor.zeros_like(params.get("w")), "b": tensor.zeros_like(params.get("b"))} for params in
            self.network_params]

    def train(self, inputs: tensor.array, outputs: tensor.array) -> None:
        self.init_network_params(inputs.shape)
        for _ in tqdm(range(self.epochs), desc="Training the model"):
            loss: float = 0.0
            batch_num: int = 1
            for batch in self.iterator(inputs, outputs):
                grads: List[Dict[str, tensor.array]] = self.grad_fn(self.network_params, batch.inputs, batch.outputs)
                for i, layer_params in enumerate(grads):
                    self.momentum_params[i]["w"] = (self.beta * self.momentum_params[i]["w"] + (
                            1 - self.beta * layer_params.get("w"))) / (1 - self.beta ** batch_num)
                    self.momentum_params[i]["b"] = (self.beta * self.momentum_params[i]["b"] + (
                            1 - self.beta * layer_params.get("b"))) / (1 - self.beta ** batch_num)
                    self.network_params[i]["w"] -= self.lr * self.momentum_params[i]["w"]
                    self.network_params[i]["b"] -= self.lr * self.momentum_params[i]["b"]
                batch_num += 1
                loss += self.compute_cost(self.network_params, batch.inputs, batch.outputs)
            self.cost.append(loss)
            self.accuracy.append(self.evaluate(inputs, outputs))
