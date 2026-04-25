
class SmartPlantCard extends HTMLElement {
  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <ha-card>
          <div class="container">
            <div class="image-container">
              <img id="plant-image" src="" alt="Plant">
              <div class="overlay">
                <div class="header">
                  <h2 id="plant-name"></h2>
                  <p id="plant-species"></p>
                </div>
                <div class="stats">
                  <div class="stat">
                    <ha-icon icon="mdi:water"></ha-icon>
                    <span id="next-watering"></span>
                  </div>
                  <div class="stat">
                    <ha-icon id="health-icon" icon="mdi:heart"></ha-icon>
                    <span id="health-status"></span>
                  </div>
                </div>
                <button id="water-button" class="water-btn">
                  <ha-icon icon="mdi:water-pump"></ha-icon>
                  Mark Watered
                </button>
              </div>
            </div>
          </div>
          <style>
            ha-card {
              overflow: hidden;
              border-radius: 16px;
              background: var(--card-background-color);
              position: relative;
              height: 100%;
            }
            .container {
              position: relative;
              width: 100%;
              aspect-ratio: 4 / 5;
            }
            .image-container {
              position: absolute;
              top: 0; left: 0; width: 100%; height: 100%;
            }
            #plant-image {
              width: 100%;
              height: 100%;
              object-fit: cover;
              transition: transform 0.5s ease;
            }
            .container:hover #plant-image {
              transform: scale(1.05);
            }
            .overlay {
              position: absolute;
              bottom: 0; left: 0; right: 0;
              padding: 20px;
              background: linear-gradient(transparent, rgba(0,0,0,0.8));
              color: white;
              display: flex;
              flex-direction: column;
              gap: 12px;
            }
            .header h2 {
              margin: 0;
              font-size: 1.6rem;
              font-weight: 700;
              text-shadow: 0 2px 4px rgba(0,0,0,0.5);
            }
            .header p {
              margin: 0;
              font-size: 0.9rem;
              opacity: 0.8;
              font-style: italic;
            }
            .stats {
              display: flex;
              gap: 16px;
            }
            .stat {
              display: flex;
              align-items: center;
              gap: 6px;
              font-size: 0.9rem;
              font-weight: 500;
            }
            .stat ha-icon {
              --mdc-icon-size: 18px;
            }
            .water-btn {
              background: #03a9f4;
              color: white;
              border: none;
              padding: 10px 16px;
              border-radius: 12px;
              font-weight: 600;
              font-size: 0.9rem;
              cursor: pointer;
              display: flex;
              align-items: center;
              justify-content: center;
              gap: 8px;
              transition: all 0.2s ease;
              box-shadow: 0 4px 12px rgba(3, 169, 244, 0.3);
            }
            .water-btn:hover {
              background: #039be5;
              transform: translateY(-2px);
              box-shadow: 0 6px 16px rgba(3, 169, 244, 0.4);
            }
            .water-btn:active {
              transform: translateY(0);
            }
          </style>
        </ha-card>
      `;
      this.content = this.querySelector('.container');
      this.querySelector('#water-button').onclick = () => this._waterPlant();
    }

    const config = this._config;
    const entityId = config.entity;
    const state = hass.states[entityId];

    if (!state) {
      this.content.innerHTML = `<p style="padding: 16px;">Entity not found: ${entityId}</p>`;
      return;
    }

    // Get related entities
    const deviceId = state.attributes.device_id; // This might not be directly available
    // We assume standard naming or use config for other entities
    const name = state.attributes.friendly_name.split(' ')[0] || "Plant";
    const species = state.attributes.species || "";
    
    // Find image entity for this device
    const imgEntityId = entityId.replace('binary_sensor.', 'image.').replace('_needs_water', '_picture');
    const imgState = hass.states[imgEntityId] || hass.states[config.image_entity];
    const imgUrl = imgState ? imgState.attributes.entity_picture : "";

    const nextWateringId = entityId.replace('binary_sensor.', 'sensor.').replace('_needs_water', '_next_watering');
    const nextWateringState = hass.states[nextWateringId];
    
    const healthId = entityId.replace('binary_sensor.', 'select.').replace('_needs_water', '_health');
    const healthState = hass.states[healthId];

    this.querySelector('#plant-name').textContent = name;
    this.querySelector('#plant-species').textContent = species;
    this.querySelector('#plant-image').src = imgUrl || "/static/images/card_media_placeholder.png";
    this.querySelector('#next-watering').textContent = nextWateringState ? this._formatDate(nextWateringState.state) : "Unknown";
    this.querySelector('#health-status').textContent = healthState ? healthState.state : "Unknown";
    
    // Set health icon color
    const healthIcon = this.querySelector('#health-icon');
    if (healthState) {
      const h = healthState.state.toLowerCase();
      if (h.includes('excellent')) healthIcon.style.color = '#4caf50';
      else if (h.includes('good')) healthIcon.style.color = '#8bc34a';
      else healthIcon.style.color = '#f44336';
    }

    this._hass = hass;
  }

  _formatDate(dateStr) {
    if (!dateStr || dateStr === 'unknown') return "N/A";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.ceil((date - now) / (1000 * 60 * 60 * 24));
    
    if (diff === 0) return "Dnes";
    if (diff === 1) return "Zítra";
    if (diff < 0) return `Zpoždění ${Math.abs(diff)} dní!`;
    return `za ${diff} dní`;
  }

  _waterPlant() {
    const buttonId = this._config.entity.replace('binary_sensor.', 'button.').replace('_needs_water', '_mark_watered');
    this._hass.callService('button', 'press', { entity_id: buttonId });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity');
    }
    this._config = config;
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('smart-plant-card', SmartPlantCard);
