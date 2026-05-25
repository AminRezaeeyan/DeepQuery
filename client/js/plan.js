// Configuration
const API_BASE_URL = 'http://127.0.0.1:8000/api/subscriptions'; // Update this to match your Django URLs
const getAuthHeaders = () => {
    const token = localStorage.getItem('access');
    return {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '' 
    };
};

document.addEventListener('DOMContentLoaded', () => {
    fetchCurrentSubscription();
    fetchPlans();
});

async function fetchCurrentSubscription() {
    try {
        // Adjust endpoint based on your urls.py for MySubscriptionView
        const response = await fetch(`${API_BASE_URL}/my-subscription/`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const data = await response.json();
            if (data && data.is_active) {
                document.getElementById('current-subscription-section').classList.remove('hidden');
                document.getElementById('current-plan-name').textContent = data.plan.name;
                document.getElementById('current-plan-status').textContent = 'Active';
                document.getElementById('current-plan-date').textContent = new Date(data.end_date).toLocaleDateString();
            }
        }
    } catch (error) {
        console.error('Error fetching subscription:', error);
    }
}

async function fetchPlans() {
    try {
        // Adjust endpoint based on your urls.py for PlanViewSet
        const response = await fetch(`${API_BASE_URL}/plans/`, {
            headers: { 'Content-Type': 'application/json' }
        });

        if (response.ok) {
            const plans = await response.json();
            renderPlans(plans);
        } else {
            console.error('Failed to load plans');
        }
    } catch (error) {
        console.error('Error fetching plans:', error);
    }
}

function renderPlans(plans) {
    const container = document.getElementById('plans-container');
    container.innerHTML = '';

    plans.forEach(plan => {
        const card = document.createElement('div');
        card.className = 'card plan-card';
        
        card.innerHTML = `
            <h2>${plan.name}</h2>
            <div class="plan-price">${plan.price} IRR</div>
            <ul class="plan-features">
                <li>Message Limit: ${plan.daily_message_limit} / day</li>
                <li>Document Limit: ${plan.daily_document_limit} / day</li>
                <li>Image Limit: ${plan.daily_image_limit} / day</li>
            </ul>
            <button onclick="initiatePayment(${plan.id})">Subscribe Now</button>
        `;
        
        container.appendChild(card);
    });
}

async function initiatePayment(planId) {
    try {
        const button = event.target;
        button.textContent = 'Processing...';
        button.disabled = true;

        // Adjust endpoint based on your urls.py for PaymentView
        const response = await fetch(`${API_BASE_URL}/payment/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ plan_id: planId })
        });

        if (response.ok) {
            const data = await response.json();
            // Assuming your backend returns a dictionary with the Zarinpal payment URL
            if (data.payment_url) { 
                window.location.href = data.payment_url;
            } else {
                alert('Payment URL not provided by the server.');
                button.textContent = 'Subscribe Now';
                button.disabled = false;
            }
        } else {
            const errData = await response.json();
            alert(`Error: ${JSON.stringify(errData)}`);
            button.textContent = 'Subscribe Now';
            button.disabled = false;
        }
    } catch (error) {
        console.error('Error initiating payment:', error);
        alert('A network error occurred.');
    }
}
