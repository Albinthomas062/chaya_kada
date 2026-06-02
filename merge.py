import re

def process_html():
    with open('stitch_ui.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # Add Django tags
    html = "{% load static %}\n" + html

    # Add HLS.js to head
    html = html.replace('</head>', '  <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>\n</head>')

    # Replace video img with actual video player
    video_replacement = """
    <div class="relative w-full aspect-video rounded-xl overflow-hidden bg-black ring-1 ring-white/10 group">
        <video id="player" class="w-full h-full object-cover" controls autoplay></video>
        
        <!-- Controls overlay when not playing -->
        <div id="video-overlay" class="absolute inset-0 flex flex-col justify-between p-4 bg-gradient-to-t from-black/80 via-transparent to-transparent pointer-events-none transition-opacity duration-300">
            <div class="flex justify-between items-start pointer-events-auto">
                <div class="flex gap-2">
                    <span class="bg-secondary-container/80 backdrop-blur-md text-white text-[10px] font-bold px-2 py-0.5 rounded-sm uppercase">LIVE IPTV</span>
                </div>
            </div>
            
            <div class="flex flex-col gap-4 pointer-events-auto">
                <div class="flex items-center gap-4 w-full">
                    <select id="channel-list" class="flex-grow bg-black/60 border border-white/20 text-white rounded p-2 text-sm">
                        <option value="">Loading Channels...</option>
                    </select>
                    <button id="load-btn" class="bg-primary text-black px-4 py-2 rounded font-bold text-sm">Play</button>
                    <label class="text-white text-xs flex items-center gap-1 cursor-pointer">
                        <input type="checkbox" id="use-proxy"> Proxy
                    </label>
                </div>
            </div>
        </div>
    </div>
    """
    
    # regex to replace the <div class="relative ..."> ... </div> containing the img
    html = re.sub(r'<div class="relative w-full aspect-video rounded-xl overflow-hidden bg-black ring-1 ring-white/10 group">.*?</div>\s*<!-- Channel Selection Overlay -->\s*<div.*?</div>\s*</div>', video_replacement, html, flags=re.DOTALL)


    # Replace the static grid of seats with a Django template loop
    seat_grid_replacement = """
    <div class="grid grid-cols-5 gap-y-8 gap-x-4 place-items-center w-full">
        {% for seat in seats %}
        {% if seat.occupant %}
        <div class="flex flex-col items-center opacity-50 cursor-not-allowed group relative" data-seat="{{ seat.seat_number }}">
            <span class="material-symbols-outlined text-on-surface" style="font-variation-settings: 'FILL' 1;">chair</span>
            <span class="text-[10px] mt-1 text-outline">{{ seat.seat_number }}</span>
            <div class="absolute -bottom-6 text-[9px] bg-black px-1 rounded text-white whitespace-nowrap">{{ seat.occupant.username }}</div>
        </div>
        {% else %}
        <button class="flex flex-col items-center group transition-all duration-300 seat-btn" data-seat="{{ seat.seat_number }}" onclick="takeSeat({{ seat.seat_number }})">
            <span class="material-symbols-outlined text-outline group-hover:text-primary">chair</span>
            <span class="text-[10px] mt-1 text-outline">{{ seat.seat_number }}</span>
        </button>
        {% endif %}
        {% endfor %}
    </div>
    """
    html = re.sub(r'<div class="grid grid-cols-5 gap-y-8 gap-x-4 place-items-center">.*?</div>', seat_grid_replacement, html, flags=re.DOTALL)


    # Replace chat log with empty log to be filled by WS
    chat_log_replacement = """
    <div class="p-4 flex flex-col gap-4 flex-grow overflow-y-auto min-h-[220px]" id="chat-log">
        <div class="flex flex-col gap-1 items-center">
            <span class="text-[12px] text-white/40">Welcome to Theatre {{ room.name }}!</span>
        </div>
    </div>
    """
    html = re.sub(r'<div class="p-4 flex flex-col gap-4 max-h-\[220px\] overflow-y-auto" id="chat-stream">.*?</div>', chat_log_replacement, html, flags=re.DOTALL)

    # Replace Chat form input
    chat_input_replacement = """
    <div class="p-4 bg-black/60 border-t border-white/5 mt-auto">
        <form id="chat-form" class="flex gap-2">
            <input id="chat-input" class="flex-grow bg-surface-container-lowest border border-outline-variant focus:border-primary focus:ring-1 focus:ring-primary/20 rounded-lg text-sm text-on-surface px-4 py-2 outline-none transition-all" placeholder="Join the conversation..." type="text" autocomplete="off" required/>
            <button type="submit" class="bg-primary text-on-primary w-10 h-10 flex items-center justify-center rounded-lg active:scale-95 transition-transform">
                <span class="material-symbols-outlined">send</span>
            </button>
        </form>
    </div>
    """
    html = re.sub(r'<div class="p-4 bg-black/60 border-t border-white/5 mt-auto">.*?</div>', chat_input_replacement, html, flags=re.DOTALL)

    # Change nav links
    html = html.replace('href="#"', 'href="/"')
    html = html.replace('<a class="flex flex-col items-center justify-center text-primary bg-primary/10 rounded-full px-6 py-2 shadow-[0_0_20px_rgba(212,175,55,0.2)] scale-105 transition-all duration-300 ease-out" href="/">', '<a class="flex flex-col items-center justify-center text-primary bg-primary/10 rounded-full px-6 py-2 shadow-[0_0_20px_rgba(212,175,55,0.2)] scale-105 transition-all duration-300 ease-out" href="{% url \'find_chat\' %}">')

    # Add Javascript logic for WS and IPTV at the end
    script_logic = """
    <script>
    const roomId = "{{ room.room_id }}";
    const currentUsername = "{{ request.user.username }}";
    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    
    // WebSocket Connection
    const chatSocket = new WebSocket(
        wsScheme + '://' + window.location.host + '/ws/theatre/' + roomId + '/'
    );

    chatSocket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        if (data.action === 'chat_message') {
            const chatLog = document.getElementById('chat-log');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'flex flex-col gap-1';
            msgDiv.innerHTML = `
                <span class="text-[10px] font-label-md text-primary uppercase">${data.username}</span>
                <p class="text-[13px] text-on-surface-variant font-body-md bg-white/5 p-3 rounded-lg rounded-tl-none">${data.message}</p>
            `;
            chatLog.appendChild(msgDiv);
            chatLog.scrollTop = chatLog.scrollHeight;
        } 
        else if (data.action === 'seat_update') {
            window.location.reload(); // Simple reload to update seats layout
        }
    };

    chatSocket.onclose = function(e) {
        console.error('Chat socket closed unexpectedly');
    };

    // Chat Form Submit
    document.getElementById('chat-form').onsubmit = function(e) {
        e.preventDefault();
        const messageInputDom = document.getElementById('chat-input');
        const message = messageInputDom.value;
        chatSocket.send(JSON.stringify({
            'action': 'chat_message',
            'message': message
        }));
        messageInputDom.value = '';
    };

    // Take Seat
    function takeSeat(seatNumber) {
        chatSocket.send(JSON.stringify({
            'action': 'take_seat',
            'seat_number': seatNumber
        }));
    }

    // IPTV Loading Logic
    const video = document.getElementById('player');
    const overlay = document.getElementById('video-overlay');
    let hls = null;
    
    // Fetch channels
    fetch('https://iptv-org.github.io/iptv/index.m3u')
        .then(res => res.text())
        .then(text => {
            const lines = text.split('\\n');
            const select = document.getElementById('channel-list');
            select.innerHTML = '<option value="">Select a Channel...</option>';
            
            for(let i=0; i<lines.length; i++){
                if(lines[i].startsWith('#EXTINF')){
                    const parts = lines[i].split(',');
                    const name = parts[1] || 'Unknown Channel';
                    const url = lines[i+1];
                    if (url && url.trim() !== '') {
                        const option = document.createElement('option');
                        option.value = url.trim();
                        option.textContent = name;
                        select.appendChild(option);
                    }
                }
            }
        })
        .catch(err => {
            console.error('Failed to load IPTV playlist', err);
        });

    document.getElementById('load-btn').onclick = function() {
        let streamUrl = document.getElementById('channel-list').value;
        if (!streamUrl) {
            alert('Please select a channel first.');
            return;
        }
        
        const useProxy = document.getElementById('use-proxy').checked;
        if (useProxy) {
            streamUrl = '/proxy-m3u/?url=' + encodeURIComponent(streamUrl);
        }

        if (Hls.isSupported()) {
            if (hls) hls.destroy();
            hls = new Hls();
            hls.loadSource(streamUrl);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function() {
                video.play().catch(e => console.log('Autoplay blocked'));
            });
            hls.on(Hls.Events.ERROR, function(event, data) {
                if (data.fatal && data.type === Hls.ErrorTypes.NETWORK_ERROR && !useProxy) {
                    alert("Network error. Try checking the 'Proxy' box and playing again.");
                }
            });
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = streamUrl;
            video.addEventListener('loadedmetadata', function() { video.play(); });
        }
    };
    
    // Hide overlay when playing
    video.addEventListener('play', () => {
        overlay.style.opacity = '0';
        document.getElementById('screen-glow').style.opacity = '1';
    });
    video.addEventListener('pause', () => {
        overlay.style.opacity = '1';
        document.getElementById('screen-glow').style.opacity = '0.3';
    });
    </script>
    """
    
    html = re.sub(r'<script>.*?</script>\s*</body>', script_logic + '\n</body>', html, flags=re.DOTALL)

    # Save to theatre_room.html
    with open(r'chatkada\templates\theatre_room.html', 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    process_html()
