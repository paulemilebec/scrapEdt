function copyToClipboard() {
  const copyText = document.getElementById("calendarUrl");
  const copyStatus = document.getElementById("copyStatus");
  const copyButton = document.getElementById("copyButton");

  if (!copyText || !copyStatus || !copyButton) {
    return;
  }

  navigator.clipboard.writeText(copyText.value).then(() => {
    copyStatus.textContent = "Lien copie dans le presse-papiers.";
    copyButton.textContent = "Copie";
    setTimeout(() => {
      copyButton.textContent = "Copier le lien";
    }, 1400);
  }).catch(() => {
    copyStatus.textContent = "Impossible de copier automatiquement. Selectionnez le lien et copiez-le manuellement.";
  });
}

document.addEventListener("DOMContentLoaded", () => {
  const copyButton = document.getElementById("copyButton");
  if (copyButton) {
    copyButton.addEventListener("click", copyToClipboard);
  }
});
