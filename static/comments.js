document.addEventListener('DOMContentLoaded', function() {
  function openComments(postId) {
    const modal = document.getElementById('comments-modal');
    const postIdInput = document.getElementById('comment-post-id');
    const list = document.getElementById('comments-list');
    postIdInput.value = postId;
    list.innerHTML = 'Loading...';
    // show and animate modal
    modal.style.display = 'block';
    const content = modal.querySelector('.comments-modal-content');
    if (content) {
      content.style.opacity = '0';
      content.style.transform = 'scale(0.96) translateY(-6px)';
      content.style.transition = 'transform 180ms ease-out, opacity 180ms ease-out';
      requestAnimationFrame(() => {
        content.style.opacity = '1';
        content.style.transform = 'scale(1) translateY(0)';
      });
    }

    fetch(`/comments/${postId}`)
      .then(r => {
        if (!r.ok) throw new Error('Network response was not ok');
        return r.json();
      })
      .then(data => {
        list.innerHTML = '';
        if (data.comments && data.comments.length) {
          data.comments.forEach(c => {
            const div = document.createElement('div');
            div.style.borderBottom = '1px solid #222';
            div.style.padding = '8px 0';
            const header = document.createElement('div');
            header.style.display = 'flex';
            header.style.justifyContent = 'space-between';
            header.style.alignItems = 'center';
            // left: avatar + username link
            const left = document.createElement('div');
            left.style.display = 'flex';
            left.style.alignItems = 'center';
            const avatar = document.createElement('div');
            avatar.className = 'avatar-badge';
            // Always render initials for privacy and consistency
            const initials = (c.username || '').trim().slice(0,2).toUpperCase();
            avatar.textContent = initials || '?';
            const userLink = document.createElement('a');
            userLink.href = '/profile/' + encodeURIComponent(c.username);
            userLink.textContent = c.username;
            userLink.style.color = '#9fd4ff';
            userLink.style.textDecoration = 'none';
            userLink.style.fontWeight = '600';
            left.appendChild(avatar);
            left.appendChild(userLink);
            const ts = document.createElement('small');
            ts.style.color = '#9aa0a6';
            ts.style.fontSize = '0.85rem';
            ts.textContent = c.timestamp;
            header.appendChild(left);
            header.appendChild(ts);
            const contentDiv = document.createElement('div');
            contentDiv.textContent = c.content; // safe insertion
            contentDiv.style.color = '#ddd';
            contentDiv.style.marginTop = '6px';
            list.appendChild(div);
            div.appendChild(header);
            div.appendChild(contentDiv);
          });
        } else {
          list.innerHTML = '<p style="color:#666;">No comments yet. Be the first to comment!</p>';
        }
      })
      .catch(err => {
        console.error('Failed to load comments', err);
        list.innerHTML = '<p style="color:#900">Could not load comments. Please try again.</p>';
      });
  }

  function closeComments() {
    const modal = document.getElementById('comments-modal');
    const content = modal.querySelector('.comments-modal-content');
    if (content) {
      content.style.opacity = '0';
      content.style.transform = 'scale(0.98) translateY(-6px)';
      setTimeout(() => { modal.style.display = 'none'; }, 180);
    } else {
      modal.style.display = 'none';
    }
  }

  // Delegate click for comment buttons
  document.body.addEventListener('click', function(e) {
    if (e.target && e.target.matches('.comment-btn')) {
      const postId = e.target.getAttribute('data-post-id');
      openComments(postId);
    }
  });

  const closeBtn = document.getElementById('close-comments');
  if (closeBtn) closeBtn.addEventListener('click', closeComments);

  const commentForm = document.getElementById('comment-form');
  if (commentForm) {
    commentForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const postId = document.getElementById('comment-post-id').value;
      const content = document.getElementById('comment-content').value.trim();
      if (!content) return;
      const formData = new URLSearchParams();
      formData.append('post_id', postId);
      formData.append('content', content);
      fetch('/add_comment', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: formData.toString()
      })
      .then(r => {
        if (!r.ok) return r.json().then(j => Promise.reject(j));
        return r.json();
      })
      .then(data => {
        if (data.success) {
          document.getElementById('comment-content').value = '';
          // refresh comments
          fetch(`/comments/${postId}`, {credentials: 'same-origin'})
            .then(r => {
              if (!r.ok) throw new Error('Failed to fetch comments');
              return r.json();
            })
            .then(data => {
              const list = document.getElementById('comments-list');
              list.innerHTML = '';
              if (data.comments && data.comments.length) {
                data.comments.forEach(c => {
                  const div = document.createElement('div');
                  div.style.borderBottom = '1px solid #222';
                  div.style.padding = '8px 0';
                  const header = document.createElement('div');
                  header.style.display = 'flex';
                  header.style.justifyContent = 'space-between';
                  header.style.alignItems = 'center';
                  // left: avatar + username link
                  const left = document.createElement('div');
                  left.style.display = 'flex';
                  left.style.alignItems = 'center';
                  const avatar = document.createElement('div');
                  avatar.className = 'avatar-badge';
                  // Always render initials for privacy and consistency
                  const initials = (c.username || '').trim().slice(0,2).toUpperCase();
                  avatar.textContent = initials || '?';
                  const userLink = document.createElement('a');
                  userLink.href = '/profile/' + encodeURIComponent(c.username);
                  userLink.textContent = c.username;
                  userLink.style.color = '#9fd4ff';
                  userLink.style.textDecoration = 'none';
                  userLink.style.fontWeight = '600';
                  left.appendChild(avatar);
                  left.appendChild(userLink);
                  const ts = document.createElement('small');
                  ts.style.color = '#9aa0a6';
                  ts.style.fontSize = '0.85rem';
                  ts.textContent = c.timestamp;
                  header.appendChild(left);
                  header.appendChild(ts);
                  const contentDiv = document.createElement('div');
                  contentDiv.textContent = c.content;
                  contentDiv.style.color = '#ddd';
                  contentDiv.style.marginTop = '6px';
                  div.appendChild(header);
                  div.appendChild(contentDiv);
                  list.appendChild(div);
                });
              }
              // update comment count badge if exists
              const badge = document.getElementById('comment-count-' + postId);
              if (badge) {
                badge.textContent = data.comments ? data.comments.length : 0;
              }
            })
            .catch(err => console.error('Failed to refresh comments', err));
        } else if (data.error) {
          alert(data.error || 'Could not post comment');
        }
      })
      .catch(err => {
        console.error('Error posting comment', err);
        alert((err && err.error) ? err.error : 'Could not post comment');
      });
    });
  }
});