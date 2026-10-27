<template><span class="s-spinner" aria-hidden="true" /></template>

<style>
.s-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #7566e52b;
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: s-spinner-spin 0.7s linear infinite;
}
@keyframes s-spinner-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
