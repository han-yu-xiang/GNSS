# Conditional Partially Pooled 3-D GMM Model-Fit Report

Status: `BUILT_PENDING_INDEPENDENT_QA`
Selected K: `3`
Selected pooling kappa: `16.0`
Primary Doppler variable: `absolute_relative_doppler_magnitude_hz`

The model uses shared component covariances, environment-specific means, and environment--elevation mixture weights with partial pooling. The global model is a regularization parent and is not an all-path paper conclusion.

Scene-LOSO selected mean weighted NLPD: `3.25715`
Scene-LOSO selected mean energy score: `3.23978`
Signed-minus-absolute energy difference across selected-fold sensitivity: mean `0.0521061`, 95% empirical interval `[-0.0604334, 0.245859]`.

The signed sensitivity remains an internal decision gate. A GMM component is not assigned a reflector or physical propagation identity. The model is not a complete stochastic channel model.

Execution boundary: raw IQ, MATLAB, SAGE, batch, Stage4 sources, formal manuscript, figures, tables, Evidence Matrix, and handoffs were not modified.
