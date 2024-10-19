var profile;
var issend = false;
function initializeLiff(myLiffId) {
    liff
        .init({
            liffId: myLiffId
        })
        .then(() => {
            initializeApp();
        })
        .catch((err) => {
            console.log(err);
            alert('啟動失敗。');
        });
}

function initializeApp() {
    liff.getProfile()
        .then(gprofile => {
            profile = gprofile;
            const name = profile.displayName;

            var h = document.getElementById('h');
            h.innerHTML = 'Hello!!' + name;
            var profileImg = document.getElementById('profileImg');
            profileImg.src = profile.pictureUrl;
            profileImg.style.display = 'block';

        })
        .catch((err) => {
            console.log('error', err);
        });

}


$("#btnSave").click(function () {
    alert('btnSave');
    try {
        $.ajax({
            url: '/line/create_profile',
            method: 'POST',
            data: JSON.stringify({
                user_id: profile.userId,
                user_name: profile.displayName,
                user_picture: profile.pictureUrl
            },),
            contentType: "application/json; charset=utf-8",
            traditional: true,
            success: function (data) {
                console.log(data);
                if (!issend) {
                    issend = true;
                    liff.sendMessages([
                        {
                            type: 'text',
                            text: '我完成了！'
                        }
                    ])
                        .then(() => {
                            console.log('message sent');
                            liff.closeWindow()

                        })
                        .catch((err) => {
                            console.log('error', err);
                        });
                }


            }
        })

    } catch (err) {
        alert(err);
    }





});

initializeLiff('2006474745-ObYjRxE8');