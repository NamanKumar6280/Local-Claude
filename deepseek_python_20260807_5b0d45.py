import os
import sys

# Dictionary mapping relative file paths to their exact complete contents
FILES = {}

# -----------------------------------------------------------------------------
# 1. PACKAGES & CONFIGURATION FILES
# -----------------------------------------------------------------------------

FILES["Packages/manifest.json"] = """{
  "dependencies": {
    "com.unity.render-pipelines.universal": "14.0.8",
    "com.unity.ugui": "1.0.0",
    "com.unity.modules.ai": "1.0.0",
    "com.unity.modules.audio": "1.0.0",
    "com.unity.modules.animation": "1.0.0",
    "com.unity.modules.physics": "1.0.0",
    "com.unity.modules.ui": "1.0.0",
    "com.unity.modules.vehicles": "1.0.0"
  }
}"""

FILES["ProjectSettings/ProjectSettings.asset"] = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!129 &1
PlayerSettings:
  m_ObjectHideFlags: 0
  serializedVersion: 22
  companyName: DefaultCompany
  productName: The Cousins Secret
  defaultCursor: {fileID: 0}
  cursorHotspot: {x: 0, y: 0}
  m_BuildTargetIcons: []
  m_BuildTargetPlatformIcons: []
  m_BuildTargetBatching: []
  m_GraphicsAPIs: []
  m_DefaultGraphicsAPIs: {}
  m_BuildTargetGraphicsAPIs: []
  m_BuildTargetPreferredNativeResolutions: []
  m_BuildTargetResolutionScales: []
  m_BuildTargetSupportedAspectRatios: []
  m_AndroidTargetArchitectures: 2
  m_AndroidMinSdkVersion: 24
  m_AndroidTargetSdkVersion: 33
  m_ScriptingBackend: 1
  m_ActiveInputHandler: 0
"""

FILES["ProjectSettings/QualitySettings.asset"] = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!47 &1
QualitySettings:
  m_ObjectHideFlags: 0
  serializedVersion: 14
  m_CurrentQuality: 1
  m_QualitySettings:
  - m_Name: URP Mobile Optimized
    m_VSyncCount: 0
    m_TargetFrameRate: 60
    m_ShadowDistance: 25.0
    m_TextureQuality: 0
    m_AnisotropicTextures: 0
    m_AntiAliasing: 0
    m_SoftParticles: 0
    m_RealtimeReflectionProbes: 0
    m_BillboardsFaceCameraPosition: 0
"""

FILES["ProjectSettings/TagManager.asset"] = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!78 &1
TagManager:
  serializedVersion: 2
  tags:
  - Player
  - Monster
  - Interactable
  - Key
  - HideSpot
  layers:
  - Default
  - TransparentFX
  - Ignore Raycast
  - Water
  - UI
  - Player
  - Monster
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  - 
  m_SortingLayers:
  - name: Default
    uniqueID: 0
    locked: 0
"""

# -----------------------------------------------------------------------------
# 2. ASSEMBLY DEFINITIONS
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/Core/Game.Core.asmdef"] = """{
    "name": "Game.Core",
    "rootNamespace": "Game.Core",
    "references": [
        "GUID:15fc0a57446b3144c949da3e2b9737a9",
        "GUID:df380645f10b7bc4b97d4f5eb63018e6"
    ],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}"""

FILES["Assets/Scripts/Player/Game.Player.asmdef"] = """{
    "name": "Game.Player",
    "rootNamespace": "Game.Player",
    "references": [
        "Game.Core"
    ],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}"""

FILES["Assets/Scripts/AI/Game.AI.asmdef"] = """{
    "name": "Game.AI",
    "rootNamespace": "Game.AI",
    "references": [
        "Game.Core",
        "Game.Player"
    ],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}"""

FILES["Assets/Scripts/UI/Game.UI.asmdef"] = """{
    "name": "Game.UI",
    "rootNamespace": "Game.UI",
    "references": [
        "Game.Core",
        "Game.Player"
    ],
    "includePlatforms": [],
    "excludePlatforms": [],
    "allowUnsafeCode": false,
    "overrideReferences": false,
    "precompiledReferences": [],
    "autoReferenced": true,
    "defineConstraints": [],
    "versionDefines": [],
    "noEngineReferences": false
}"""

# -----------------------------------------------------------------------------
# 3. CORE & MANAGERS
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/Core/GameManager.cs"] = """using System;
using UnityEngine;

namespace Game.Core
{
    public enum GameState
    {
        CinematicIntro,
        Exploration,
        Chase,
        Jumpscare,
        GameOver,
        Victory,
        CinematicOutro
    }

    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        public GameState CurrentState { get; private set; } = GameState.CinematicIntro;

        public event Action<GameState> OnGameStateChanged;

        [Header("Game Progression Flags")]
        public bool HasWaterBottle = false;
        public bool SawLevitation = false;
        public bool HouseKeyFound = false;
        public bool MainDoorUnlocked = false;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        public void SetState(GameState newState)
        {
            if (CurrentState == newState) return;

            CurrentState = newState;
            Debug.Log($"[GameManager] Game State Changed To: {newState}");
            OnGameStateChanged?.Invoke(newState);

            if (newState == GameState.Jumpscare || newState == GameState.GameOver)
            {
                Time.timeScale = 1.0f;
            }
        }

        public void TriggerJumpscare()
        {
            if (CurrentState == GameState.GameOver || CurrentState == GameState.Victory) return;
            SetState(GameState.Jumpscare);
        }

        public void TriggerGameOver()
        {
            SetState(GameState.GameOver);
        }

        public void TriggerVictory()
        {
            SetState(GameState.Victory);
        }
    }
}
"""

FILES["Assets/Scripts/Core/AudioManager.cs"] = """using UnityEngine;

namespace Game.Core
{
    public class AudioManager : MonoBehaviour
    {
        public static AudioManager Instance { get; private set; }

        [Header("Audio Sources")]
        [SerializeField] private AudioSource ambientSource;
        [SerializeField] private AudioSource heartbeatSource;
        [SerializeField] private AudioSource sfxSource;

        [Header("Audio Clips")]
        [SerializeField] private AudioClip ambientHorrorClip;
        [SerializeField] private AudioClip heartbeatClip;
        [SerializeField] private AudioClip jumpscareSound;
        [SerializeField] private AudioClip doorOpenSound;
        [SerializeField] private AudioClip doorLockedSound;
        [SerializeField] private AudioClip itemPickupSound;

        private float targetPitch = 1.0f;
        private float targetVolume = 0.0f;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);

            InitSources();
        }

        private void InitSources()
        {
            if (ambientSource == null) ambientSource = gameObject.AddComponent<AudioSource>();
            if (heartbeatSource == null) heartbeatSource = gameObject.AddComponent<AudioSource>();
            if (sfxSource == null) sfxSource = gameObject.AddComponent<AudioSource>();

            ambientSource.loop = true;
            ambientSource.playOnAwake = false;
            
            heartbeatSource.loop = true;
            heartbeatSource.clip = heartbeatClip;
            heartbeatSource.volume = 0f;
            heartbeatSource.playOnAwake = false;
            if (heartbeatClip != null) heartbeatSource.Play();
        }

        private void Update()
        {
            if (heartbeatSource != null && heartbeatSource.isPlaying)
            {
                heartbeatSource.volume = Mathf.Lerp(heartbeatSource.volume, targetVolume, Time.deltaTime * 3f);
                heartbeatSource.pitch = Mathf.Lerp(heartbeatSource.pitch, targetPitch, Time.deltaTime * 3f);
            }
        }

        public void UpdateHeartbeat(float monsterDistance, float maxDistance = 15f)
        {
            if (monsterDistance >= maxDistance)
            {
                targetVolume = 0f;
                targetPitch = 1f;
            }
            else
            {
                float t = 1f - Mathf.Clamp01(monsterDistance / maxDistance);
                targetVolume = Mathf.Lerp(0.2f, 1.0f, t);
                targetPitch = Mathf.Lerp(0.8f, 1.8f, t);
            }
        }

        public void PlaySFX(AudioClip clip, float volume = 1.0f)
        {
            if (clip != null && sfxSource != null)
            {
                sfxSource.PlayOneShot(clip, volume);
            }
        }

        public void PlayJumpscareSound() => PlaySFX(jumpscareSound, 1.0f);
        public void PlayDoorOpen() => PlaySFX(doorOpenSound, 0.8f);
        public void PlayDoorLocked() => PlaySFX(doorLockedSound, 0.8f);
        public void PlayPickup() => PlaySFX(itemPickupSound, 0.8f);
    }
}
"""

FILES["Assets/Scripts/Core/HorrorFXManager.cs"] = """using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Game.Core
{
    public class HorrorFXManager : MonoBehaviour
    {
        public static HorrorFXManager Instance { get; private set; }

        [SerializeField] private Volume globalVolume;
        private Vignette vignette;
        private ChromaticAberration chromaticAberration;
        private FilmGrain filmGrain;

        private float targetVignette = 0.25f;
        private float targetChroma = 0.1f;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;

            if (globalVolume == null)
            {
                globalVolume = GetComponent<Volume>();
            }

            if (globalVolume != null && globalVolume.profile != null)
            {
                globalVolume.profile.TryGet(out vignette);
                globalVolume.profile.TryGet(out chromaticAberration);
                globalVolume.profile.TryGet(out filmGrain);
            }
        }

        private void Update()
        {
            if (vignette != null)
            {
                vignette.intensity.value = Mathf.Lerp(vignette.intensity.value, targetVignette, Time.deltaTime * 4f);
            }

            if (chromaticAberration != null)
            {
                chromaticAberration.intensity.value = Mathf.Lerp(chromaticAberration.intensity.value, targetChroma, Time.deltaTime * 4f);
            }
        }

        public void SetProximityEffect(float normalizedDanger)
        {
            normalizedDanger = Mathf.Clamp01(normalizedDanger);
            targetVignette = Mathf.Lerp(0.25f, 0.65f, normalizedDanger);
            targetChroma = Mathf.Lerp(0.05f, 0.85f, normalizedDanger);
        }

        public void SetJumpscareIntensity()
        {
            targetVignette = 0.9f;
            targetChroma = 1.0f;
        }
    }
}
"""

# -----------------------------------------------------------------------------
# 4. INTERACTION & INVENTORY
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/Interaction/IInteractable.cs"] = """namespace Game.Interaction
{
    public interface IInteractable
    {
        string PromptText { get; }
        bool CanInteract { get; }
        void Interact();
    }
}
"""

FILES["Assets/Scripts/Interaction/InteractionManager.cs"] = """using UnityEngine;
using UnityEngine.UI;
using Game.Interaction;
using Game.Core;

namespace Game.Interaction
{
    public class InteractionManager : MonoBehaviour
    {
        [Header("Raycast Settings")]
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float rayDistance = 3.0f;
        [SerializeField] private LayerMask interactableLayer;

        [Header("UI Prompts")]
        [SerializeField] private Text promptText;
        [SerializeField] private Image crosshairImage;

        private IInteractable currentInteractable;

        private void Update()
        {
            if (GameManager.Instance != null && GameManager.Instance.CurrentState != GameState.Exploration && GameManager.Instance.CurrentState != GameState.Chase)
            {
                ClearInteractable();
                return;
            }

            PerformRaycast();

            if (currentInteractable != null && (Input.GetKeyDown(KeyCode.E) || Input.GetMouseButtonDown(0)))
            {
                if (currentInteractable.CanInteract)
                {
                    currentInteractable.Interact();
                }
            }
        }

        private void PerformRaycast()
        {
            if (playerCamera == null) playerCamera = Camera.main;
            if (playerCamera == null) return;

            Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);
            if (Physics.Raycast(ray, out RaycastHit hit, rayDistance, interactableLayer))
            {
                IInteractable interactable = hit.collider.GetComponent<IInteractable>();
                if (interactable == null) interactable = hit.collider.GetComponentInParent<IInteractable>();

                if (interactable != null && interactable.CanInteract)
                {
                    currentInteractable = interactable;
                    if (promptText != null)
                    {
                        promptText.gameObject.SetActive(true);
                        promptText.text = interactable.PromptText;
                    }
                    if (crosshairImage != null) crosshairImage.color = Color.red;
                    return;
                }
            }

            ClearInteractable();
        }

        public void TriggerInteraction()
        {
            if (currentInteractable != null && currentInteractable.CanInteract)
            {
                currentInteractable.Interact();
            }
        }

        private void ClearInteractable()
        {
            currentInteractable = null;
            if (promptText != null) promptText.gameObject.SetActive(false);
            if (crosshairImage != null) crosshairImage.color = Color.white;
        }
    }
}
"""

FILES["Assets/Scripts/Interaction/DoorController.cs"] = """using UnityEngine;
using Game.Interaction;
using Game.Core;
using Game.Inventory;

namespace Game.Interaction
{
    public class DoorController : MonoBehaviour, IInteractable
    {
        [Header("Door Settings")]
        [SerializeField] private bool isLocked = false;
        [SerializeField] private string requiredKeyID = "HouseKey";
        [SerializeField] private float openAngle = 90f;
        [SerializeField] private float speed = 3f;

        [Header("Messages")]
        [SerializeField] private string openPrompt = "Open Door";
        [SerializeField] private string closePrompt = "Close Door";
        [SerializeField] private string lockedPrompt = "Door Locked (Key Needed)";

        private bool isOpen = false;
        private Quaternion closedRotation;
        private Quaternion targetRotation;

        public string PromptText => isLocked ? lockedPrompt : (isOpen ? closePrompt : openPrompt);
        public bool CanInteract => true;

        private void Awake()
        {
            closedRotation = transform.localRotation;
            targetRotation = closedRotation;
        }

        private void Update()
        {
            transform.localRotation = Quaternion.Slerp(transform.localRotation, targetRotation, Time.deltaTime * speed);
        }

        public void Interact()
        {
            if (isLocked)
            {
                if (InventorySystem.Instance != null && InventorySystem.Instance.HasItem(requiredKeyID))
                {
                    isLocked = false;
                    InventorySystem.Instance.RemoveItem(requiredKeyID);
                    if (AudioManager.Instance != null) AudioManager.Instance.PlayDoorOpen();
                    ToggleDoor();
                }
                else
                {
                    if (AudioManager.Instance != null) AudioManager.Instance.PlayDoorLocked();
                }
            }
            else
            {
                if (AudioManager.Instance != null) AudioManager.Instance.PlayDoorOpen();
                ToggleDoor();
            }
        }

        private void ToggleDoor()
        {
            isOpen = !isOpen;
            targetRotation = isOpen ? closedRotation * Quaternion.Euler(0, openAngle, 0) : closedRotation;
        }
    }
}
"""

FILES["Assets/Scripts/Inventory/ItemData.cs"] = """using UnityEngine;

namespace Game.Inventory
{
    public enum ItemType { Key, Lockpick, Fuse, WaterBottle }

    [CreateAssetMenu(fileName = "NewItemData", menuName = "HorrorGame/ItemData")]
    public class ItemData : ScriptableObject
    {
        public string itemID;
        public string itemName;
        public ItemType type;
        public Sprite icon;
    }
}
"""

FILES["Assets/Scripts/Inventory/InventorySystem.cs"] = """using System.Collections.Generic;
using UnityEngine;
using Game.Core;

namespace Game.Inventory
{
    public class InventorySystem : MonoBehaviour
    {
        public static InventorySystem Instance { get; private set; }

        private HashSet<string> items = new HashSet<string>();

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        public bool AddItem(string itemID)
        {
            if (string.IsNullOrEmpty(itemID) || items.Contains(itemID)) return false;
            
            items.Add(itemID);
            Debug.Log($"[InventorySystem] Picked up item: {itemID}");
            if (AudioManager.Instance != null) AudioManager.Instance.PlayPickup();
            return true;
        }

        public bool HasItem(string itemID) => items.Contains(itemID);

        public bool RemoveItem(string itemID)
        {
            if (items.Contains(itemID))
            {
                items.Remove(itemID);
                return true;
            }
            return false;
        }
    }
}
"""

# -----------------------------------------------------------------------------
# 5. PLAYER CONTROLLER & JOYSTICK
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/Player/VirtualJoystick.cs"] = """using UnityEngine;
using UnityEngine.EventSystems;

namespace Game.Player
{
    public class VirtualJoystick : MonoBehaviour, IDragHandler, IPointerDownHandler, IPointerUpHandler
    {
        [SerializeField] private RectTransform containerRect;
        [SerializeField] private RectTransform handleRect;
        [SerializeField] private float handleRange = 100f;

        public Vector2 Direction { get; private set; } = Vector2.zero;

        public void OnPointerDown(PointerEventData eventData)
        {
            OnDrag(eventData);
        }

        public void OnDrag(PointerEventData eventData)
        {
            if (containerRect == null || handleRect == null) return;

            Vector2 position = RectTransformUtility.WorldToScreenPoint(null, containerRect.position);
            Vector2 radius = containerRect.sizeDelta / 2f;
            Direction = (eventData.position - position) / (radius * (handleRange / 100f));
            
            if (Direction.magnitude > 1.0f)
            {
                Direction = Direction.normalized;
            }

            handleRect.anchoredPosition = Direction * (radius * (handleRange / 100f));
        }

        public void OnPointerUp(PointerEventData eventData)
        {
            Direction = Vector2.zero;
            if (handleRect != null) handleRect.anchoredPosition = Vector2.zero;
        }
    }
}
"""

FILES["Assets/Scripts/Player/PlayerController.cs"] = """using UnityEngine;
using Game.Core;

namespace Game.Player
{
    public enum MovementNoiseState { Silent, Walking, Sprinting }

    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        [Header("Movement Options")]
        [SerializeField] private float walkSpeed = 3.0f;
        [SerializeField] private float sprintSpeed = 5.5f;
        [SerializeField] private float crouchSpeed = 1.5f;
        [SerializeField] private float gravity = -19.62f;

        [Header("Stamina Mechanics")]
        [SerializeField] private float maxStamina = 100f;
        [SerializeField] private float staminaDrainRate = 25f;
        [SerializeField] private float staminaRegenRate = 15f;
        private float currentStamina;

        [Header("Look Controls")]
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float mouseSensitivity = 2.0f;
        [SerializeField] private VirtualJoystick joystick;

        [Header("Head Bobbing")]
        [SerializeField] private float bobSpeed = 10f;
        [SerializeField] private float bobAmount = 0.05f;

        private CharacterController controller;
        private Vector3 velocity;
        private float xRotation = 0f;
        private float defaultHeight;
        private Vector3 defaultCamPos;
        private float timer = 0f;

        public MovementNoiseState CurrentNoise { get; private set; } = MovementNoiseState.Silent;

        private void Awake()
        {
            controller = GetComponent<CharacterController>();
            defaultHeight = controller.height;
            if (playerCamera == null) playerCamera = GetComponentInChildren<Camera>();
            if (playerCamera != null) defaultCamPos = playerCamera.transform.localPosition;
            currentStamina = maxStamina;
        }

        private void Update()
        {
            if (GameManager.Instance != null && GameManager.Instance.CurrentState != GameState.Exploration && GameManager.Instance.CurrentState != GameState.Chase)
            {
                return;
            }

            HandleLook();
            HandleMovement();
            HandleHeadBob();
        }

        private void HandleLook()
        {
#if UNITY_EDITOR || UNITY_STANDALONE
            if (Input.GetMouseButton(1) || Cursor.lockState == CursorLockMode.Locked)
            {
                float mouseX = Input.GetAxis("Mouse X") * mouseSensitivity;
                float mouseY = Input.GetAxis("Mouse Y") * mouseSensitivity;

                xRotation -= mouseY;
                xRotation = Mathf.Clamp(xRotation, -80f, 80f);

                if (playerCamera != null) playerCamera.transform.localRotation = Quaternion.Euler(xRotation, 0f, 0f);
                transform.Rotate(Vector3.up * mouseX);
            }
#endif
        }

        private void HandleMovement()
        {
            bool isGrounded = controller.isGrounded;
            if (isGrounded && velocity.y < 0) velocity.y = -2f;

            float moveX = joystick != null ? joystick.Direction.x : Input.GetAxis("Horizontal");
            float moveZ = joystick != null ? joystick.Direction.y : Input.GetAxis("Vertical");

            bool isCrouching = Input.GetKey(KeyCode.LeftControl);
            bool isSprinting = Input.GetKey(KeyCode.LeftShift) && currentStamina > 0 && (moveX != 0 || moveZ != 0) && !isCrouching;

            float currentSpeed = walkSpeed;

            if (isCrouching)
            {
                currentSpeed = crouchSpeed;
                controller.height = Mathf.Lerp(controller.height, defaultHeight * 0.5f, Time.deltaTime * 8f);
                CurrentNoise = MovementNoiseState.Silent;
            }
            else
            {
                controller.height = Mathf.Lerp(controller.height, defaultHeight, Time.deltaTime * 8f);
                if (isSprinting)
                {
                    currentSpeed = sprintSpeed;
                    currentStamina -= staminaDrainRate * Time.deltaTime;
                    CurrentNoise = MovementNoiseState.Sprinting;
                }
                else
                {
                    if (currentStamina < maxStamina) currentStamina += staminaRegenRate * Time.deltaTime;
                    CurrentNoise = (moveX != 0 || moveZ != 0) ? MovementNoiseState.Walking : MovementNoiseState.Silent;
                }
            }

            currentStamina = Mathf.Clamp(currentStamina, 0f, maxStamina);

            Vector3 move = transform.right * moveX + transform.forward * moveZ;
            controller.Move(move * currentSpeed * Time.deltaTime);

            velocity.y += gravity * Time.deltaTime;
            controller.Move(velocity * Time.deltaTime);
        }

        private void HandleHeadBob()
        {
            if (playerCamera == null) return;

            if (Mathf.Abs(controller.velocity.x) > 0.1f || Mathf.Abs(controller.velocity.z) > 0.1f)
            {
                timer += Time.deltaTime * bobSpeed;
                playerCamera.transform.localPosition = new Vector3(
                    defaultCamPos.x + Mathf.Sin(timer) * bobAmount,
                    defaultCamPos.y + Mathf.Sin(timer * 2) * bobAmount,
                    defaultCamPos.z
                );
            }
            else
            {
                timer = 0;
                playerCamera.transform.localPosition = Vector3.Lerp(playerCamera.transform.localPosition, defaultCamPos, Time.deltaTime * 5f);
            }
        }
    }
}
"""

# -----------------------------------------------------------------------------
# 6. MONSTER AI
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/AI/CousinAI.cs"] = """using UnityEngine;
using UnityEngine.AI;
using Game.Core;
using Game.Player;

namespace Game.AI
{
    public enum AIState { Patrol, Investigate, Chase, Stun, Attack }

    [RequireComponent(typeof(NavMeshAgent))]
    public class CousinAI : MonoBehaviour
    {
        [Header("Perception")]
        [SerializeField] private float viewDistance = 12f;
        [SerializeField] private float viewAngle = 60f;
        [SerializeField] private LayerMask obstacleMask;

        [Header("Speeds")]
        [SerializeField] private float patrolSpeed = 2.0f;
        [SerializeField] private float chaseSpeed = 4.5f;

        [Header("Patrol Points")]
        [SerializeField] private Transform[] patrolWaypoints;

        private NavMeshAgent agent;
        private Transform playerTransform;
        private PlayerController playerController;
        private AIState currentState = AIState.Patrol;
        private int currentWaypointIndex = 0;
        private Vector3 lastNoisePosition;

        private void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
            GameObject playerObj = GameObject.FindGameObjectWithTag("Player");
            if (playerObj != null)
            {
                playerTransform = playerObj.transform;
                playerController = playerObj.GetComponent<PlayerController>();
            }
        }

        private void Update()
        {
            if (GameManager.Instance != null && 
               (GameManager.Instance.CurrentState == GameState.CinematicIntro || GameManager.Instance.CurrentState == GameState.CinematicOutro))
            {
                agent.isStopped = true;
                return;
            }

            CheckSensoryInput();

            switch (currentState)
            {
                case AIState.Patrol:
                    UpdatePatrol();
                    break;
                case AIState.Investigate:
                    UpdateInvestigate();
                    break;
                case AIState.Chase:
                    UpdateChase();
                    break;
                case AIState.Stun:
                    break;
                case AIState.Attack:
                    break;
            }

            if (playerTransform != null && AudioManager.Instance != null)
            {
                float dist = Vector3.Distance(transform.position, playerTransform.position);
                AudioManager.Instance.UpdateHeartbeat(dist);
                if (HorrorFXManager.Instance != null)
                {
                    HorrorFXManager.Instance.SetProximityEffect(1.0f - Mathf.Clamp01(dist / 15f));
                }
            }
        }

        private void CheckSensoryInput()
        {
            if (playerTransform == null) return;

            float distToPlayer = Vector3.Distance(transform.position, playerTransform.position);

            if (CanSeePlayer(distToPlayer))
            {
                SetState(AIState.Chase);
                return;
            }

            if (playerController != null && currentState != AIState.Chase)
            {
                float hearingRadius = playerController.CurrentNoise switch
                {
                    MovementNoiseState.Sprinting => 16f,
                    MovementNoiseState.Walking => 7f,
                    _ => 0f
                };

                if (distToPlayer <= hearingRadius)
                {
                    lastNoisePosition = playerTransform.position;
                    SetState(AIState.Investigate);
                }
            }
        }

        private bool CanSeePlayer(float distance)
        {
            if (distance > viewDistance) return false;

            Vector3 dirToPlayer = (playerTransform.position - transform.position).normalized;
            if (Vector3.Angle(transform.forward, dirToPlayer) < viewAngle / 2f)
            {
                if (!Physics.Raycast(transform.position + Vector3.up, dirToPlayer, distance, obstacleMask))
                {
                    return true;
                }
            }
            return false;
        }

        private void SetState(AIState newState)
        {
            if (currentState == newState) return;
            currentState = newState;

            switch (newState)
            {
                case AIState.Patrol:
                    agent.speed = patrolSpeed;
                    agent.isStopped = false;
                    if (GameManager.Instance.CurrentState == GameState.Chase)
                        GameManager.Instance.SetState(GameState.Exploration);
                    break;
                case AIState.Investigate:
                    agent.speed = patrolSpeed;
                    agent.SetDestination(lastNoisePosition);
                    agent.isStopped = false;
                    break;
                case AIState.Chase:
                    agent.speed = chaseSpeed;
                    agent.isStopped = false;
                    GameManager.Instance.SetState(GameState.Chase);
                    break;
            }
        }

        private void UpdatePatrol()
        {
            if (patrolWaypoints == null || patrolWaypoints.Length == 0) return;

            if (!agent.pathPending && agent.remainingDistance < 0.5f)
            {
                currentWaypointIndex = (currentWaypointIndex + 1) % patrolWaypoints.Length;
                agent.SetDestination(patrolWaypoints[currentWaypointIndex].position);
            }
        }

        private void UpdateInvestigate()
        {
            if (!agent.pathPending && agent.remainingDistance < 0.8f)
            {
                SetState(AIState.Patrol);
            }
        }

        private void UpdateChase()
        {
            agent.SetDestination(playerTransform.position);
            float dist = Vector3.Distance(transform.position, playerTransform.position);

            if (dist < 1.3f)
            {
                ExecuteAttack();
            }
            else if (dist > viewDistance * 1.5f)
            {
                SetState(AIState.Patrol);
            }
        }

        private void ExecuteAttack()
        {
            currentState = AIState.Attack;
            agent.isStopped = true;
            if (AudioManager.Instance != null) AudioManager.Instance.PlayJumpscareSound();
            if (HorrorFXManager.Instance != null) HorrorFXManager.Instance.SetJumpscareIntensity();
            if (GameManager.Instance != null) GameManager.Instance.TriggerJumpscare();
        }

        public void Stun(float duration)
        {
            StartCoroutine(StunRoutine(duration));
        }

        private System.Collections.IEnumerator StunRoutine(float duration)
        {
            AIState previousState = currentState;
            currentState = AIState.Stun;
            agent.isStopped = true;
            yield return new WaitForSeconds(duration);
            agent.isStopped = false;
            SetState(previousState);
        }
    }
}
"""

# -----------------------------------------------------------------------------
# 7. CINEMATICS & OUTRO
# -----------------------------------------------------------------------------

FILES["Assets/Scripts/Core/IntroCinematicController.cs"] = """using System.Collections;
using UnityEngine;
using Game.Core;

namespace Game.Core
{
    public class IntroCinematicController : MonoBehaviour
    {
        [Header("Cinematic Elements")]
        [SerializeField] private Camera cinematicCamera;
        [SerializeField] private Camera playerCamera;
        [SerializeField] private Transform cousinTransform;
        [SerializeField] private Transform levitationTarget;

        [Header("Timings")]
        [SerializeField] private float levitationSpeed = 1.0f;

        private void Start()
        {
            if (GameManager.Instance != null)
            {
                StartCoroutine(RunIntroSequence());
            }
        }

        private IEnumerator RunIntroSequence()
        {
            GameManager.Instance.SetState(GameState.CinematicIntro);
            if (cinematicCamera != null) cinematicCamera.gameObject.SetActive(true);
            if (playerCamera != null) playerCamera.gameObject.SetActive(false);

            yield return new WaitForSeconds(1.5f);

            // Levitating cousin sequence
            if (cousinTransform != null && levitationTarget != null)
            {
                Vector3 startPos = cousinTransform.position;
                float t = 0;
                while (t < 1.0f)
                {
                    t += Time.deltaTime * levitationSpeed;
                    cousinTransform.position = Vector3.Lerp(startPos, levitationTarget.position, Mathf.SmoothStep(0, 1, t));
                    yield return null;
                }
            }

            yield return new WaitForSeconds(2.0f);

            // Snap camera cut back to player
            if (cinematicCamera != null) cinematicCamera.gameObject.SetActive(false);
            if (playerCamera != null) playerCamera.gameObject.SetActive(true);

            GameManager.Instance.SetState(GameState.Exploration);
        }

        public void TriggerOutroSequence()
        {
            StartCoroutine(RunOutroSequence());
        }

        private IEnumerator RunOutroSequence()
        {
            GameManager.Instance.SetState(GameState.CinematicOutro);
            Debug.Log("[Cinematic] Running Outro: Escaped house... parents arrive... checking inside...");
            yield return new WaitForSeconds(3.0f);
            GameManager.Instance.TriggerVictory();
        }
    }
}
"""

# -----------------------------------------------------------------------------
# 8. EDITOR SETUP WIZARD SCRIPT
# -----------------------------------------------------------------------------

FILES["Assets/Editor/SceneSetupWizard.cs"] = """using UnityEditor;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Rendering;
using Game.Core;
using Game.Player;
using Game.AI;
using Game.Interaction;
using Game.Inventory;

namespace Game.Editor
{
    public class SceneSetupWizard : EditorWindow
    {
        [MenuItem("Tools/Build Complete Horror Game Scene")]
        public static void GenerateScene()
        {
            // 1. Create Core Manager Hierarchy
            GameObject managersObj = new GameObject("[Managers]");
            managersObj.AddComponent<GameManager>();
            managersObj.AddComponent<AudioManager>();
            managersObj.AddComponent<HorrorFXManager>();
            managersObj.AddComponent<InventorySystem>();

            // 2. Setup Post Processing Volume
            GameObject volumeObj = new GameObject("Global PostProcess Volume");
            Volume vol = volumeObj.AddComponent<Volume>();
            vol.isGlobal = true;

            // 3. Environment Environment/House
            GameObject houseFloor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            houseFloor.name = "HouseFloor";
            houseFloor.transform.localScale = new Vector3(3, 1, 3);
            houseFloor.layer = LayerMask.NameToLayer("Default");

            // Static for NavMesh
            GameObjectUtility.SetStaticEditorFlags(houseFloor, StaticEditorFlags.NavigationStatic);

            // 4. Setup Player
            GameObject player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            player.name = "PlayerCapsule";
            player.tag = "Player";
            player.layer = LayerMask.NameToLayer("Player");
            player.transform.position = new Vector3(0, 1.1f, 0);

            CharacterController controller = player.AddComponent<CharacterController>();
            controller.center = new Vector3(0, 0, 0);
            controller.height = 2.0f;

            GameObject camObj = new GameObject("PlayerCamera");
            camObj.transform.SetParent(player.transform);
            camObj.transform.localPosition = new Vector3(0, 0.6f, 0);
            Camera cam = camObj.AddComponent<Camera>();
            camObj.AddComponent<AudioListener>();

            player.AddComponent<PlayerController>();
            player.AddComponent<InteractionManager>();

            // 5. Setup Monster (Cousin)
            GameObject monster = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            monster.name = "CousinMonster";
            monster.tag = "Monster";
            monster.layer = LayerMask.NameToLayer("Monster");
            monster.transform.position = new Vector3(8f, 1.1f, 8f);

            Renderer ren = monster.GetComponent<Renderer>();
            if (ren != null) ren.sharedMaterial.color = Color.red;

            monster.AddComponent<NavMeshAgent>();
            monster.AddComponent<CousinAI>();

            // 6. Setup Door & Key
            GameObject door = GameObject.CreatePrimitive(PrimitiveType.Cube);
            door.name = "MainExitDoor";
            door.transform.position = new Vector3(0, 1.25f, 14.5f);
            door.transform.localScale = new Vector3(2f, 2.5f, 0.2f);
            door.layer = LayerMask.NameToLayer("Interactable");
            door.AddComponent<DoorController>();

            // Bake NavMesh automatically
            UnityEditor.AI.NavMeshBuilder.BuildNavMesh();

            Debug.Log("[SceneSetupWizard] Successfully built horror scene hierarchy, navigation mesh, and game systems!");
        }
    }
}
"""

def main():
    print("--------------------------------------------------")
    print("  Generating Horror Game Unity Project Codebase...")
    print("--------------------------------------------------")

    for file_path, content in FILES.items():
        dir_name = os.path.dirname(file_path)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")

        print(f"[CREATED] {file_path}")

    print("--------------------------------------------------")
    print("Project Generation Complete!")
    print("You can now open this folder in Unity or zip it for your GitHub Actions build pipeline.")

if __name__ == "__main__":
    main()
