function initializeLiff(myLiffId) {
    liff
        .init({
            liffId: myLiffId
        })
        .then(() => {
            initializeApp();
        })
        .catch((err) => {
            print(err);
            alert('啟動失敗。');
        });
}

function initializeApp() {
    var h = document.getElementById('result');
    h.innerHTML = 'Hello!!';
}

initializeLiff('2006474745-g2rn5ZE4');