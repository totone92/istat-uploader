self.addEventListener("message", ({ data }) => {
  setTimeout(() => self.postMessage(data.id), data.ms);
});
