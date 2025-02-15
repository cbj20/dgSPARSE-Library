import torch
from torch import nn
import os
from scipy.io import mmread
from dgsparse import spmm_sum
from dgsparse import SparseTensor
from torch_sparse import spmm


class SpMMSum:
    def __init__(self, path, in_dim, device) -> None:
        sparsecsr = mmread(path).astype("float32").tocsr()
        rowptr = torch.from_numpy(sparsecsr.indptr).to(device).int()
        colind = torch.from_numpy(sparsecsr.indices).to(device).int()
        weight = torch.from_numpy(sparsecsr.data).to(device).float()
        sparsecoo = sparsecsr.tocoo()

        # prepare for pytorch_sparse
        row = torch.from_numpy(sparsecoo.row).type(torch.int64)
        col = torch.from_numpy(sparsecoo.col).type(torch.int64)
        index = torch.cat((row.unsqueeze(0), col.unsqueeze(0)), 0)
        self.index = index.to(device)
        self.m = sparsecoo.shape[0]
        self.n = sparsecoo.shape[1]
        self.weight = weight
        print(self.m)
        print(self.n)

        # prepare for torch and dgsparse
        self.tcsr = torch.sparse_csr_tensor(rowptr, colind, weight, dtype=torch.float)
        self.dcsr = SparseTensor.from_torch_sparse_csr_tensor(self.tcsr, True)
        nodes = rowptr.size(0) - 1
        self.nodes = nodes
        self.in_dim = in_dim
        self.device = device
        self.input_feature = torch.rand(
            (nodes, in_dim), requires_grad=True, device=device
        )
        # don't use copy to device, or may can not implement backward_check

    def forward_check(self):
        out_check = torch.sparse.mm(self.tcsr, self.input_feature)
        out = spmm_sum(self.dcsr, self.input_feature)
        assert torch.allclose(out, out_check) == True

    def backward_check(self):
        out_check = spmm(self.index, self.weight, self.m, self.n, self.input_feature)
        out_check.sum().backward()
        dX_check = self.input_feature.grad

        out = spmm_sum(self.dcsr, self.input_feature)
        out.sum().backward()
        dX = self.input_feature.grad
        assert torch.allclose(dX, dX_check) == True


def test_spmm():
    gc = SpMMSum("../example/data/p2p-Gnutella31.mtx", 32, 0)
    gc.forward_check()
    gc.backward_check()
    # gc.calculate()
